from typing import ClassVar, Literal

import pytest
from pydantic import ValidationError

from core.target import (
    DuplicateObservedPointError,
    DuplicateTargetTypeError,
    NoUpstreamError,
    Observation,
    ObservedPoint,
    Target,
    TargetInUseError,
    TargetManager,
    TargetNotFoundError,
    TargetTypeChangeError,
    UnknownObservedPointError,
    UnknownTargetTypeError,
    UnsupportedObservedPointError,
    type_name,
)
from plugins.observed_points.position import Position
from plugins.target.aircraft import Aircraft
from tests.core.target.conftest import Subscriber
from tests.core.target.fakes import (
    InMemoryObservableTargetRepository,
    InMemoryTargetRepository,
    StaticUpstreamCatalog,
)


class DraughtObservation(Observation):
    metres: float


class Draught(ObservedPoint):
    """船特有的观察点：吃水。"""

    name: ClassVar[str] = "draught"
    observation: ClassVar[type[Observation]] = DraughtObservation


class Ship(Target, frozen=True):
    """船和飞机共用 Position 观察点。"""

    observed_points: ClassVar[tuple[type[ObservedPoint], ...]] = (Position, Draught)
    type: Literal["ship"] = "ship"
    mmsi: str


# ---------------------------------------------------------------- 类型


def test_register_type_twice_rejected(manager: TargetManager) -> None:
    with pytest.raises(DuplicateTargetTypeError):
        manager.register_type(Aircraft)


def test_observed_points_are_collected_from_types(manager: TargetManager) -> None:
    manager.register_type(Ship)
    assert manager.get_observed_point("position") is Position
    assert manager.get_observed_point("draught") is Draught
    assert set(manager.observed_points()) == {Position, Draught}


def test_observed_point_name_clash_rejected(manager: TargetManager) -> None:
    class XObservation(Observation):
        x: float

    class OtherPosition(ObservedPoint):
        name: ClassVar[str] = "position"
        observation: ClassVar[type[Observation]] = XObservation

    class Car(Target, frozen=True):
        observed_points: ClassVar[tuple[type[ObservedPoint], ...]] = (OtherPosition,)
        type: Literal["car"] = "car"

    with pytest.raises(DuplicateObservedPointError):
        manager.register_type(Car)
    with pytest.raises(UnknownTargetTypeError):  # 注册失败不留半截
        manager.get_type("car")


def test_shared_observed_point_across_types() -> None:
    upstreams = StaticUpstreamCatalog(
        {("aircraft", "position"): ["adsb"], ("ship", "position"): ["ais"]}
    )
    m = TargetManager(InMemoryTargetRepository(), InMemoryObservableTargetRepository(), upstreams)
    m.register_type(Aircraft)
    m.register_type(Ship)
    m.upsert_target(Aircraft(id="a1", name="x", registration="B-1"))
    m.upsert_target(Ship(id="s1", name="y", mmsi="412000000"))

    plane, ship = m.get_observable("a1", "position"), m.get_observable("s1", "position")
    assert plane.observed_point is ship.observed_point is Position
    assert (plane.upstreams, ship.upstreams) == (("adsb",), ("ais",))


def test_subclass_must_narrow_type() -> None:
    class Untyped(Target, frozen=True):
        pass

    assert type_name(Aircraft) == "aircraft"
    with pytest.raises(TypeError):
        type_name(Untyped)


def test_attributes_are_validated_on_construction() -> None:
    with pytest.raises(ValidationError):
        Aircraft(id="t1", name="x")  # type: ignore[call-arg]  # 缺注册号
    assert Aircraft(id="t1", name="x", registration="B-1").attributes() == {
        "registration": "B-1",
        "icao24": None,
    }


def test_parse_dispatches_on_type(manager: TargetManager) -> None:
    target = manager.parse({"type": "aircraft", "id": "t1", "name": "x", "registration": "B-1"})
    assert isinstance(target, Aircraft)
    assert target.registration == "B-1"
    with pytest.raises(UnknownTargetTypeError):
        manager.parse({"type": "ship", "id": "t1", "name": "x"})
    with pytest.raises(ValidationError):
        manager.parse({"type": "aircraft", "id": "t1", "name": "x"})


# ---------------------------------------------------------------- 目标


def test_upsert_stores_type_agnostic_record(
    manager: TargetManager, targets: InMemoryTargetRepository
) -> None:
    manager.upsert_target(Aircraft(id="t1", name="x", registration="B-1", aliases=["A"]))
    record = targets.items["t1"]
    assert record.type == "aircraft"
    assert record.attributes == {"registration": "B-1", "icao24": None}

    restored = manager.get_target("t1")
    assert isinstance(restored, Aircraft)
    assert restored == Aircraft(id="t1", name="x", registration="B-1", aliases=["A"])


def test_upsert_target_unregistered_type(manager: TargetManager) -> None:
    with pytest.raises(UnknownTargetTypeError):
        manager.upsert_target(Ship(id="t1", name="x", mmsi="1"))


def test_upsert_target_cannot_change_type(manager: TargetManager, plane: Target) -> None:
    manager.register_type(Ship)
    with pytest.raises(TargetTypeChangeError):
        manager.upsert_target(Ship(id=plane.id, name="x", mmsi="1"))


def test_find_by_alias(manager: TargetManager, plane: Target) -> None:
    assert manager.find_by_alias("MU5101") == plane
    assert manager.find_by_alias("nope") is None


# ---------------------------------------------------------------- 可观测目标


def test_get_observable_is_singleton(
    manager: TargetManager, plane: Target, observables: InMemoryObservableTargetRepository
) -> None:
    a = manager.get_observable(plane.id, "position")
    b = manager.get_observable(plane.id, "position")
    assert a is b
    assert a.id == "t1:position"
    assert a.upstreams == ("adsb",)
    assert observables.items[a.id] is a


def test_inspect_observable_does_not_create(
    manager: TargetManager, plane: Target, observables: InMemoryObservableTargetRepository
) -> None:
    point, upstreams = manager.inspect_observable(plane.id, "position")
    assert (point, upstreams) == (Position, ("adsb",))
    assert manager.find_observable("t1:position") is None
    assert observables.items == {}
    with pytest.raises(UnknownObservedPointError):
        manager.inspect_observable(plane.id, "fuel")


def test_get_observable_errors(manager: TargetManager, plane: Target) -> None:
    with pytest.raises(TargetNotFoundError):
        manager.get_observable("missing", "position")
    with pytest.raises(UnknownObservedPointError):
        manager.get_observable(plane.id, "fuel")
    manager.register_type(Ship)
    with pytest.raises(UnsupportedObservedPointError):  # 吃水是船的观察点，飞机不能被这样观测
        manager.get_observable(plane.id, "draught")


def test_get_observable_without_upstream() -> None:
    m = TargetManager(
        InMemoryTargetRepository(), InMemoryObservableTargetRepository(), StaticUpstreamCatalog({})
    )
    m.register_type(Aircraft)
    m.upsert_target(Aircraft(id="t1", name="x", registration="B"))
    with pytest.raises(NoUpstreamError):
        m.get_observable("t1", "position")


def test_active_observables_follow_referencers(manager: TargetManager, plane: Target) -> None:
    obs = manager.get_observable(plane.id, "position")
    assert manager.active_observables() == []

    sub = Subscriber()
    obs.acquire(sub, ["adsb"])
    assert manager.active_observables() == [obs]

    obs.release(sub)
    assert manager.active_observables() == []


def test_upsert_target_rebinds_live_observable(manager: TargetManager, plane: Target) -> None:
    obs = manager.get_observable(plane.id, "position")
    manager.upsert_target(plane.model_copy(update={"registration": "B-9999"}))
    assert obs.query_spec({"registration"}).query == {"registration": "B-9999"}


def test_remove_target_in_use_rejected(manager: TargetManager, plane: Target) -> None:
    obs = manager.get_observable(plane.id, "position")
    obs.acquire(Subscriber(), ["adsb"])
    with pytest.raises(TargetInUseError):
        manager.remove_target(plane.id)


def test_remove_target_clears_observables(
    manager: TargetManager,
    plane: Target,
    targets: InMemoryTargetRepository,
    observables: InMemoryObservableTargetRepository,
) -> None:
    obs = manager.get_observable(plane.id, "position")
    manager.remove_target(plane.id)
    assert plane.id not in targets.items
    assert obs.id not in observables.items
    assert manager.find_observable(obs.id) is None
