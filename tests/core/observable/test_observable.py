from datetime import UTC, datetime

import pytest

from core.observable import ObservableTarget, ObservableTargetFactory, UnsupportedUpstreamError
from core.observation import Observation, ObservationEnvelope
from core.target import Target
from plugins.observed_points.position import Position, PositionObservation
from tests.core.observable.fakes import Subscriber


def test_subscribe_is_idempotent_and_unsubscribe_tolerant(
    observable_factory: ObservableTargetFactory, plane: Target
) -> None:
    obs = observable_factory.get_observable(plane.id, "position")
    sub = Subscriber()
    obs.subscribe(sub, ["adsb"])
    obs.subscribe(sub, ["adsb"])
    assert obs.subscribers() == frozenset({sub})
    obs.unsubscribe(sub)
    obs.unsubscribe(sub)
    assert not obs.is_active


def test_subscribers_is_a_snapshot(
    observable_factory: ObservableTargetFactory, plane: Target
) -> None:
    obs = observable_factory.get_observable(plane.id, "position")
    a, b = Subscriber(), Subscriber()
    obs.subscribe(a, ["adsb"])
    obs.subscribe(b, ["adsb"])
    snapshot = obs.subscribers()
    obs.unsubscribe(a)
    assert snapshot == frozenset({a, b})


def test_accepts_only_its_observation_class(
    observable_factory: ObservableTargetFactory, plane: Target
) -> None:
    class Other(Observation):
        x: int

    obs = observable_factory.get_observable(plane.id, "position")
    assert obs.accepts(PositionObservation(lat=31.2, lon=121.3))
    assert not obs.accepts(Other(x=1))


# ---------------------------------------------------------------- 构造与按上游订阅


def test_constructor_keeps_only_the_target_id(plane: Target) -> None:
    obs = ObservableTarget(plane.id, Position)
    assert (obs.target_id, obs.observed_point, obs.id) == ("t1", Position, "t1:position")


def test_subscribe_needs_an_upstream(plane: Target) -> None:
    obs = ObservableTarget(plane.id, Position)
    with pytest.raises(UnsupportedUpstreamError):
        obs.subscribe(Subscriber(), [])
    assert not obs.is_active


def test_routing_by_upstream(plane: Target) -> None:
    obs = ObservableTarget(plane.id, Position)
    a, b = Subscriber(), Subscriber()
    obs.subscribe(a, ["adsb"])
    obs.subscribe(b, ["adsb", "radar"])

    assert obs.subscribers_for("adsb") == {a, b}
    assert obs.subscribers_for("radar") == {b}
    assert obs.subscribers_for("satellite") == frozenset()
    assert obs.active_upstreams() == ("adsb", "radar")

    obs.subscribe(b, ["satellite"])  # 再次 subscribe 替换订阅
    assert obs.subscription(b) == {"satellite"}
    assert obs.active_upstreams() == ("adsb", "satellite")

    obs.unsubscribe(a)
    obs.unsubscribe(b)
    assert obs.active_upstreams() == ()


def test_envelope_serializes_the_concrete_observation() -> None:
    envelope = ObservationEnvelope(
        observable_id="t1:position",
        upstream="adsb",
        observation=PositionObservation(lat=1, lon=2),
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        source_id="adsb#1",
    )
    assert isinstance(envelope.observation, PositionObservation)
    # 字段类型写的是基类 Observation，序列化时仍按实际类型输出全部字段
    assert envelope.model_dump()["observation"] == {"lat": 1.0, "lon": 2.0, "altitude_m": None}


def test_publish_rejects_foreign_envelopes(
    observable_factory: ObservableTargetFactory, plane: Target
) -> None:
    obs = observable_factory.get_observable(plane.id, "position")

    def envelope(observable_id: str, upstream: str) -> ObservationEnvelope:
        return ObservationEnvelope(
            observable_id=observable_id,
            upstream=upstream,
            observation=PositionObservation(lat=0, lon=0),
            occurred_at=datetime(2026, 9, 1, tzinfo=UTC),
            source_id="x",
        )

    with pytest.raises(ValueError, match="cannot publish"):
        obs.publish(envelope("other:position", "adsb"))
    assert obs.publish(envelope(obs.id, "satellite")) == 0   # 没人订阅的上游：谁也不推
