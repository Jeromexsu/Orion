from datetime import UTC, datetime
from typing import ClassVar

import pytest

from core.target import (
    ObservableTarget,
    Observation,
    ObservationEnvelope,
    ObservedPoint,
    Target,
    TargetManager,
    UnsupportedObservedPointError,
    UnsupportedUpstreamError,
)
from plugins.observed_points.position import Position, PositionObservation
from tests.core.target.conftest import Subscriber


def test_subscribe_is_idempotent_and_unsubscribe_tolerant(manager: TargetManager, plane: Target) -> None:
    obs = manager.get_observable(plane.id, "position")
    sub = Subscriber()
    obs.subscribe(sub, ["adsb"])
    obs.subscribe(sub, ["adsb"])
    assert obs.subscribers() == frozenset({sub})
    obs.unsubscribe(sub)
    obs.unsubscribe(sub)
    assert not obs.is_active


def test_subscribers_is_a_snapshot(manager: TargetManager, plane: Target) -> None:
    obs = manager.get_observable(plane.id, "position")
    a, b = Subscriber(), Subscriber()
    obs.subscribe(a, ["adsb"])
    obs.subscribe(b, ["adsb"])
    snapshot = obs.subscribers()
    obs.unsubscribe(a)
    assert snapshot == frozenset({a, b})


def test_query_spec(manager: TargetManager, plane: Target) -> None:
    spec = manager.get_observable(plane.id, "position").query_spec()
    assert spec.type == "aircraft"
    assert spec.observed_point == "position"
    assert spec.attributes["registration"] == "B-2447"
    assert spec.aliases == ["MU5101"]


def test_accepts_only_its_observation_class(manager: TargetManager, plane: Target) -> None:
    class Other(Observation):
        x: int

    obs = manager.get_observable(plane.id, "position")
    assert obs.accepts(PositionObservation(lat=31.2, lon=121.3))
    assert not obs.accepts(Other(x=1))


def test_rebind_target_rejects_other_id(manager: TargetManager, plane: Target) -> None:
    obs = manager.get_observable(plane.id, "position")
    with pytest.raises(ValueError):
        obs.rebind_target(plane.model_copy(update={"id": "t2"}))


# ---------------------------------------------------------------- 构造与按上游订阅


class FuelObservation(Observation):
    litres: float


class Fuel(ObservedPoint):
    name: ClassVar[str] = "fuel"
    observation: ClassVar[type[Observation]] = FuelObservation


def test_constructor_validates_observed_point_and_upstreams(plane: Target) -> None:
    with pytest.raises(UnsupportedObservedPointError):
        ObservableTarget(plane, Fuel, ["adsb"])
    with pytest.raises(UnsupportedUpstreamError):
        ObservableTarget(plane, Position, [])
    obs = ObservableTarget(plane, Position, ["adsb", "radar"])
    assert obs.observed_point is Position
    assert obs.id == "t1:position"


def test_subscribe_validates_upstreams(plane: Target) -> None:
    obs = ObservableTarget(plane, Position, ["adsb", "radar"])
    with pytest.raises(UnsupportedUpstreamError):
        obs.subscribe(Subscriber(), [])
    with pytest.raises(UnsupportedUpstreamError):
        obs.subscribe(Subscriber(), ["adsb", "satellite"])
    assert not obs.is_active


def test_routing_by_upstream(plane: Target) -> None:
    obs = ObservableTarget(plane, Position, ["adsb", "radar", "satellite"])
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
