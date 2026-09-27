from datetime import UTC, datetime

import pytest

from core.collector import (
    Collector,
    DuplicateUpstreamAdapterError,
    FetchedRecord,
    Query,
    UnknownUpstreamAdapterError,
    UpstreamAdapter,
    UpstreamAdapterRegistry,
    upstream_adapter,
)
from core.target import (
    ObservableTarget,
    Observation,
    ObservationEnvelope,
    ObservedPoint,
    QueryKey,
    Target,
    TargetManager,
    TargetTypeRegistry,
    observed_point,
    provides,
    query_key,
    target_type,
)
from plugins.observed_points.position import Position, PositionObservation
from plugins.query_keys.icao24 import Icao24
from plugins.query_keys.registration import Registration
from plugins.target.aircraft import Aircraft
from plugins.upstream_adapters.opensky import OpenSkyAdapter
from tests.core.collector.fakes import (
    FakeUpstreamAdapter,
    InMemoryCursorRepository,
    InMemoryObservationRepository,
)
from tests.core.target.conftest import Subscriber
from tests.core.target.fakes import InMemoryObservableTargetRepository, InMemoryTargetRepository


class FuelObservation(Observation):
    litres: float


@observed_point("fuel", observation=FuelObservation)
class Fuel(ObservedPoint): ...


@query_key("mmsi", pattern=r"^\d{9}$")
class Mmsi(QueryKey): ...


@target_type("ship", observed_points=[Position])
class Ship(Target):
    mmsi: str = provides(Mmsi)


def at(minute: int) -> datetime:
    return datetime(2026, 9, 26, 12, minute, tzinfo=UTC)


def rec(source_id: str, minute: int, lat: float = 1.0, lon: float = 2.0) -> FetchedRecord:
    return FetchedRecord(
        observation=PositionObservation(lat=lat, lon=lon), occurred_at=at(minute), source_id=source_id
    )


class Env:
    def __init__(self) -> None:
        self.adsb = FakeUpstreamAdapter("adsb")
        self.registry = UpstreamAdapterRegistry()
        self.registry.register(self.adsb)
        target_types = TargetTypeRegistry()
        target_types.register(Aircraft)
        self.manager = TargetManager(
            target_types,
            InMemoryTargetRepository(), InMemoryObservableTargetRepository(), self.registry
        )
        self.manager.upsert_target(Aircraft(id="t1", name="x", registration="B-2447"))
        self.cursors = InMemoryCursorRepository()
        self.observations = InMemoryObservationRepository()
        self.collector = Collector(
            self.manager, self.registry, self.cursors, self.observations
        )

    def observable(self) -> ObservableTarget:
        return self.manager.get_observable("t1", "position")


@pytest.fixture
def env() -> Env:
    return Env()


def test_registry_is_upstream_catalog(env: Env) -> None:
    plane = env.manager.get_target("t1")
    assert env.registry.upstreams_for(plane, Position) == ["adsb"]
    assert env.registry.upstreams_for(plane, Fuel) == []
    assert env.observable().upstreams == ("adsb",)
    with pytest.raises(DuplicateUpstreamAdapterError):
        env.registry.register(FakeUpstreamAdapter("adsb"))
    with pytest.raises(UnknownUpstreamAdapterError):
        env.registry.get("nope")


def test_upstreams_match_by_query_keys(env: Env) -> None:
    env.registry.register(FakeUpstreamAdapter("mode-s", query_key_sets=(frozenset({Icao24}),)))
    no_icao = env.manager.get_target("t1")
    with_icao = Aircraft(id="t2", name="y", registration="B-1", icao24="780abc")
    # 查询要 icao24：没有这个值的目标用不了这个上游
    assert env.registry.upstreams_for(no_icao, Position) == ["adsb"]
    assert env.registry.upstreams_for(with_icao, Position) == ["adsb", "mode-s"]


def test_one_upstream_several_query_ways() -> None:
    """同一个上游对不同目标用不同的查询方式：飞机按 ICAO 地址，船按 MMSI——上游不认识目标类型。"""
    tracker = FakeUpstreamAdapter(
        "global-track", query_key_sets=(frozenset({Icao24}), frozenset({Mmsi}))
    )
    plane = Aircraft(id="a1", name="x", registration="B-1", icao24="780abc")
    ship = Ship(id="s1", name="y", mmsi="412000000")
    bare_plane = Aircraft(id="a2", name="z", registration="B-2")

    assert tracker.choose_query(plane.query_values()) == {Icao24: "780abc"}
    assert tracker.choose_query(ship.query_values()) == {Mmsi: "412000000"}
    assert tracker.choose_query(bare_plane.query_values()) is None


def test_fetch_gets_observed_point_query_and_since(env: Env) -> None:
    env.observable().subscribe(Subscriber(), ["adsb"])
    env.collector.collect()
    (call,) = env.adsb.calls
    assert call.observed_point is Position
    assert call.query == {Registration: "B-2447"}
    assert call.since is None


def test_inactive_observables_are_not_collected(env: Env) -> None:
    env.observable()
    env.adsb.records = [rec("a#1", 1, lat=1, lon=2)]
    assert env.collector.collect() == []
    assert env.adsb.calls == []


def test_collect_validates_dedups_persists_and_publishes(env: Env) -> None:
    sub = Subscriber()
    env.observable().subscribe(sub, ["adsb"])
    env.adsb.records = [
        rec("a#2", 2, lat=31.2, lon=121.3),
        rec("a#1", 1, lat=31.0, lon=121.0),
        rec("a#1", 1, lat=31.0, lon=121.0),  # 同批重复
        # 观测类型与上游服务的观察点不符，丢弃
        FetchedRecord(observation=FuelObservation(litres=1.0), occurred_at=at(3), source_id="a#3"),
    ]
    new = env.collector.collect()

    assert [d.source_id for d in new] == ["a#1", "a#2"]
    assert new[1].observation == PositionObservation(lat=31.2, lon=121.3)
    assert env.observations.items == new
    assert sub.received == new
    assert env.cursors.get("t1:position", "adsb") == at(2).isoformat()


def test_cursor_feeds_next_query(env: Env) -> None:
    env.observable().subscribe(Subscriber(), ["adsb"])
    env.adsb.records = [rec("a#1", 1, lat=1, lon=2)]
    env.collector.collect()
    env.adsb.records.append(rec("a#2", 5, lat=1, lon=2))
    new = env.collector.collect()

    assert env.adsb.calls[0].since is None
    assert env.adsb.calls[1].since == at(1)
    assert [d.source_id for d in new] == ["a#2"]


def test_upstream_failure_is_isolated(env: Env) -> None:
    env.observable().subscribe(Subscriber(), ["adsb"])
    env.adsb.fail = True
    assert env.collector.collect() == []
    assert env.cursors.get("t1:position", "adsb") is None


def test_subscriber_failure_is_isolated(env: Env) -> None:
    class Broken:
        def on_observation(self, envelope: ObservationEnvelope) -> None:
            raise RuntimeError("boom")

    good = Subscriber()
    obs = env.observable()
    obs.subscribe(Broken(), ["adsb"])
    obs.subscribe(good, ["adsb"])
    env.adsb.records = [rec("a#1", 1, lat=1, lon=2)]

    assert len(env.collector.collect()) == 1
    assert len(good.received) == 1
    assert env.cursors.get("t1:position", "adsb") == at(1).isoformat()


def test_publish_isolates_failing_subscribers(env: Env) -> None:
    class Broken:
        def on_observation(self, envelope: ObservationEnvelope) -> None:
            raise RuntimeError("boom")

    obs = env.observable()
    good = Subscriber()
    obs.subscribe(Broken(), ["adsb"])
    obs.subscribe(good, ["adsb"])
    envelope = ObservationEnvelope(
        observable_id=obs.id,
        upstream="adsb",
        observation=PositionObservation(lat=0, lon=0),
        occurred_at=at(0),
        source_id="x",
    )
    assert obs.publish(envelope) == 1
    assert good.received == [envelope]


def test_only_subscribed_upstreams_are_fetched_and_routed(env: Env) -> None:
    radar = FakeUpstreamAdapter("radar")
    env.registry.register(radar)
    obs = env.observable()
    assert obs.upstreams == ("adsb", "radar")

    adsb_only, both = Subscriber(), Subscriber()
    obs.subscribe(adsb_only, ["adsb"])
    obs.subscribe(both, ["adsb", "radar"])
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
    obs.unsubscribe(both)
    env.collector.collect()
    assert len(radar.calls) == 1
    assert len(env.adsb.calls) == 2


def test_register_checks_adapter_declarations(env: Env) -> None:
    class NoQuery(FakeUpstreamAdapter):
        pass

    incomplete = NoQuery("no-query", query_key_sets=())
    with pytest.raises(TypeError, match="query_key_sets"):
        env.registry.register(incomplete)


def test_query_way_with_several_keys_needs_all_of_them() -> None:
    """联立查询：一种查询方式要同时提供多个查询键，缺一个就不满足，退到下一种。"""

    @query_key("callsign")
    class Callsign(QueryKey): ...

    @target_type("flight", observed_points=[Position])
    class Flight(Target):
        icao24: str | None = provides(Icao24, default=None)
        callsign: str | None = provides(Callsign, default=None)
        registration: str | None = provides(Registration, default=None)

    upstream = FakeUpstreamAdapter(
        "strict", query_key_sets=(frozenset({Icao24, Callsign}), frozenset({Registration}))
    )
    both = Flight(id="f1", name="x", icao24="780a3b", callsign="CES5101", registration="B-1")
    only_icao = Flight(id="f2", name="y", icao24="780a3b", registration="B-2")
    neither = Flight(id="f3", name="z", icao24="780a3b")

    assert upstream.choose_query(both.query_values()) == {Icao24: "780a3b", Callsign: "CES5101"}
    # 缺 Callsign，退到第二种
    assert upstream.choose_query(only_icao.query_values()) == {Registration: "B-2"}
    assert upstream.choose_query(neither.query_values()) is None


def test_one_adapter_serves_several_observed_points() -> None:
    """一个上游服务多个观察点：fetch 按观察点分支；两个可观测目标各有自己的游标。"""

    @target_type("tanker", observed_points=[Position, Fuel])
    class Tanker(Target):
        registration: str = provides(Registration)

    @upstream_adapter(observed_points=[Position, Fuel], query_key_sets=[{Registration}])
    class Provider(UpstreamAdapter):

        def __init__(self) -> None:
            self.asked: list[str] = []

        def fetch(
            self, observed_point: type[ObservedPoint], query: Query, since: datetime | None
        ) -> list[FetchedRecord]:
            self.asked.append(observed_point.name)
            observation: Observation = (
                PositionObservation(lat=1, lon=2)
                if observed_point is Position
                else FuelObservation(litres=500)
            )
            source_id = f"p#{observed_point.name}"
            return [FetchedRecord(observation=observation, occurred_at=at(1), source_id=source_id)]

    provider = Provider()
    registry = UpstreamAdapterRegistry()
    registry.register(provider)
    target_types = TargetTypeRegistry()
    target_types.register(Tanker)
    manager = TargetManager(
        target_types,
        InMemoryTargetRepository(), InMemoryObservableTargetRepository(), registry
    )
    manager.upsert_target(Tanker(id="k1", name="x", registration="B-1"))
    cursors = InMemoryCursorRepository()
    collector = Collector(
        manager, registry, cursors, InMemoryObservationRepository()
    )

    position, fuel = manager.get_observable("k1", "position"), manager.get_observable("k1", "fuel")
    assert position.upstreams == fuel.upstreams == ("provider",)
    at_position, at_fuel = Subscriber(), Subscriber()
    position.subscribe(at_position, ["provider"])
    fuel.subscribe(at_fuel, ["provider"])

    collector.collect()
    assert sorted(provider.asked) == ["fuel", "position"]
    assert [e.observation for e in at_position.received] == [PositionObservation(lat=1, lon=2)]
    assert [e.observation for e in at_fuel.received] == [FuelObservation(litres=500)]
    assert cursors.get("k1:position", "provider") == at(1).isoformat()
    assert cursors.get("k1:fuel", "provider") == at(1).isoformat()


def test_adapter_must_serve_an_observed_point(env: Env) -> None:
    with pytest.raises(TypeError, match="observed_points"):
        env.registry.register(FakeUpstreamAdapter("nothing", observed_points=frozenset()))


def test_upstream_adapter_decorator() -> None:
    assert OpenSkyAdapter.name == "openSky"   # 类名去掉 Adapter 后缀、首字母小写
    assert OpenSkyAdapter.observed_points == frozenset({Position})
    assert OpenSkyAdapter.query_key_sets == (frozenset({Icao24}),)

    with pytest.raises(TypeError, match="observed_points"):

        @upstream_adapter(observed_points=[], query_key_sets=[{Icao24}])
        class Nothing(UpstreamAdapter):  # pyright: ignore[reportUnusedClass]
            def fetch(
                self, observed_point: type[ObservedPoint], query: Query, since: datetime | None
            ) -> list[FetchedRecord]:
                return []
