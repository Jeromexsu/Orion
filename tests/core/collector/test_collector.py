from datetime import UTC, datetime

import pytest

from core.collector import (
    AdapterRegistry,
    Collector,
    Dispatcher,
    DuplicateAdapterError,
    FetchedRecord,
    UnknownAdapterError,
)
from core.target import ObservableTarget, Observation, TargetManager
from plugins.target.aircraft import Aircraft
from tests.core.collector.fakes import (
    FakeAdapter,
    InMemoryCursorRepository,
    InMemoryObservationRepository,
)
from tests.core.target.conftest import Subscriber
from tests.core.target.fakes import InMemoryObservableTargetRepository, InMemoryTargetRepository


def at(minute: int) -> datetime:
    return datetime(2026, 9, 26, 12, minute, tzinfo=UTC)


def rec(source_id: str, minute: int, **fields: object) -> FetchedRecord:
    return FetchedRecord(fields=dict(fields), occurred_at=at(minute), source_id=source_id)


class Env:
    def __init__(self) -> None:
        self.adsb = FakeAdapter("adsb", {("aircraft", "position")})
        self.registry = AdapterRegistry()
        self.registry.register(self.adsb)
        self.manager = TargetManager(
            InMemoryTargetRepository(), InMemoryObservableTargetRepository(), self.registry
        )
        self.manager.register_type(Aircraft)
        self.manager.upsert_target(Aircraft(id="t1", name="x", registration="B-2447"))
        self.cursors = InMemoryCursorRepository()
        self.observations = InMemoryObservationRepository()
        self.collector = Collector(
            self.manager, self.registry, self.cursors, self.observations, Dispatcher()
        )

    def observable(self) -> ObservableTarget:
        return self.manager.get_observable("t1", "position")


@pytest.fixture
def env() -> Env:
    return Env()


def test_registry_is_upstream_catalog(env: Env) -> None:
    assert env.registry.upstreams_for("aircraft", "position") == ["adsb"]
    assert env.registry.upstreams_for("aircraft", "fuel") == []
    assert env.observable().upstreams == ("adsb",)
    with pytest.raises(DuplicateAdapterError):
        env.registry.register(FakeAdapter("adsb", set()))
    with pytest.raises(UnknownAdapterError):
        env.registry.get("nope")


def test_inactive_observables_are_not_collected(env: Env) -> None:
    env.observable()
    env.adsb.records = [rec("a#1", 1, lat=1, lon=2)]
    assert env.collector.collect() == []
    assert env.adsb.specs == []


def test_collect_validates_dedups_persists_and_dispatches(env: Env) -> None:
    sub = Subscriber()
    env.observable().acquire(sub, ["adsb"])
    env.adsb.records = [
        rec("a#2", 2, lat="31.2", lon=121.3),
        rec("a#1", 1, lat=31.0, lon=121.0),
        rec("a#1", 1, lat=31.0, lon=121.0),  # 同批重复
        rec("a#3", 3, lat=31.4),  # 缺 lon，校验失败
    ]
    new = env.collector.collect()

    assert [d.source_id for d in new] == ["a#1", "a#2"]
    assert new[1].fields == {"lat": 31.2, "lon": 121.3, "altitude_m": None}
    assert env.observations.items == new
    assert sub.received == new
    assert env.cursors.get("t1:position", "adsb") == at(2).isoformat()


def test_cursor_feeds_next_query(env: Env) -> None:
    env.observable().acquire(Subscriber(), ["adsb"])
    env.adsb.records = [rec("a#1", 1, lat=1, lon=2)]
    env.collector.collect()
    env.adsb.records.append(rec("a#2", 5, lat=1, lon=2))
    new = env.collector.collect()

    assert env.adsb.specs[0].since is None
    assert env.adsb.specs[1].since == at(1)
    assert [d.source_id for d in new] == ["a#2"]


def test_upstream_failure_is_isolated(env: Env) -> None:
    env.observable().acquire(Subscriber(), ["adsb"])
    env.adsb.fail = True
    assert env.collector.collect() == []
    assert env.cursors.get("t1:position", "adsb") is None


def test_subscriber_failure_is_isolated(env: Env) -> None:
    class Broken:
        def on_observation(self, observation: Observation) -> None:
            raise RuntimeError("boom")

    good = Subscriber()
    obs = env.observable()
    obs.acquire(Broken(), ["adsb"])
    obs.acquire(good, ["adsb"])
    env.adsb.records = [rec("a#1", 1, lat=1, lon=2)]

    assert len(env.collector.collect()) == 1
    assert len(good.received) == 1
    assert env.cursors.get("t1:position", "adsb") == at(1).isoformat()


def test_dispatcher_counts_failures(env: Env) -> None:
    class Broken:
        def on_observation(self, observation: Observation) -> None:
            raise RuntimeError("boom")

    obs = env.observable()
    obs.acquire(Broken(), ["adsb"])
    obs.acquire(Subscriber(), ["adsb"])
    observation = Observation(
        observable_id=obs.id, upstream="adsb", fields={}, occurred_at=at(0), source_id="x"
    )
    assert Dispatcher().dispatch(obs, observation) == 1


def test_only_subscribed_upstreams_are_fetched_and_routed(env: Env) -> None:
    radar = FakeAdapter("radar", {("aircraft", "position")})
    env.registry.register(radar)
    obs = env.observable()
    assert obs.upstreams == ("adsb", "radar")

    adsb_only, both = Subscriber(), Subscriber()
    obs.acquire(adsb_only, ["adsb"])
    obs.acquire(both, ["adsb", "radar"])
    env.adsb.records = [rec("a#1", 1, lat=1, lon=2)]
    radar.records = [rec("r#1", 2, lat=1, lon=2)]

    new = env.collector.collect()
    assert [(d.source_id, d.upstream) for d in new] == [("a#1", "adsb"), ("r#1", "radar")]
    assert [d.source_id for d in adsb_only.received] == ["a#1"]
    assert [d.source_id for d in both.received] == ["a#1", "r#1"]

    # 每个上游独立游标
    assert env.cursors.get(obs.id, "adsb") == at(1).isoformat()
    assert env.cursors.get(obs.id, "radar") == at(2).isoformat()

    # 没人订阅 radar 之后不再拉取它
    obs.release(both)
    env.collector.collect()
    assert len(radar.specs) == 1
    assert len(env.adsb.specs) == 2
