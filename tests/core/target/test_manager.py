import pytest
from pydantic import ValidationError

from core.observation import Observation, ObservedPoint, observed_point
from core.target import (
    DuplicateObservedPointError,
    DuplicateTargetTypeError,
    Target,
    TargetInUseError,
    TargetManager,
    TargetNotFoundError,
    TargetTypeChangeError,
    TargetTypeRegistry,
    UnknownTargetTypeError,
    target_type,
    type_name,
)
from plugins.observed_points.position import Position
from plugins.target.aircraft import Aircraft
from tests.core.target.fakes import Draught, InMemoryTargetRepository, Ship

# ---------------------------------------------------------------- 类型


def test_register_type_twice_rejected(target_types: TargetTypeRegistry) -> None:
    with pytest.raises(DuplicateTargetTypeError):
        target_types.register(Aircraft)


def test_observed_points_are_collected_from_types(target_types: TargetTypeRegistry) -> None:
    target_types.register(Ship)
    assert target_types.get_observed_point("position") is Position
    assert target_types.get_observed_point("draught") is Draught
    assert set(target_types.observed_points()) == {Position, Draught}


def test_observed_point_name_clash_rejected(target_types: TargetTypeRegistry) -> None:
    class XObservation(Observation):
        x: float

    @observed_point("position", observation=XObservation)
    class OtherPosition(ObservedPoint): ...

    @target_type("car", observed_points=[OtherPosition])
    class Car(Target): ...

    with pytest.raises(DuplicateObservedPointError):
        target_types.register(Car)
    with pytest.raises(UnknownTargetTypeError):  # 注册失败不留半截
        target_types.get("car")


def test_target_type_must_be_declared() -> None:
    class Undeclared(Target): ...

    class Inherited(Aircraft): ...   # 只继承了父类的声明也不算

    assert type_name(Aircraft) == "aircraft"
    for cls in (Undeclared, Inherited):
        with pytest.raises(TypeError, match="@target_type"):
            type_name(cls)


def test_type_is_filled_from_declaration() -> None:
    plane = Aircraft(id="a", name="x", registration="B-1")
    assert plane.type == "aircraft"
    assert Aircraft.model_validate(plane.model_dump()) == plane
    with pytest.raises(ValidationError, match="type must be 'aircraft'"):
        Aircraft(id="a", name="x", registration="B-1", type="ship")


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


def test_upsert_target_cannot_change_type(
    manager: TargetManager, target_types: TargetTypeRegistry, plane: Target
) -> None:
    target_types.register(Ship)
    with pytest.raises(TargetTypeChangeError):
        manager.upsert_target(Ship(id=plane.id, name="x", mmsi="1"))


def test_find_by_alias(manager: TargetManager, plane: Target) -> None:
    assert manager.find_by_alias("MU5101") == plane
    assert manager.find_by_alias("nope") is None


# ---------------------------------------------------------------- 引用方


class FakeReferrer:
    def __init__(self, *refs: str) -> None:
        self.refs = list(refs)
        self.released: list[str] = []

    def references(self, target_id: str) -> list[str]:
        return self.refs

    def release(self, target_id: str) -> None:
        self.released.append(target_id)


def test_remove_target_asks_every_referrer_first(
    manager: TargetManager, plane: Target, targets: InMemoryTargetRepository
) -> None:
    idle, busy = FakeReferrer(), FakeReferrer("t1:position")
    manager.add_referrer(idle)
    manager.add_referrer(busy)
    with pytest.raises(TargetInUseError, match="t1:position"):
        manager.remove_target(plane.id)
    assert plane.id in targets.items and idle.released == []   # 有人在用：什么都不动

    busy.refs.clear()
    manager.remove_target(plane.id)
    assert plane.id not in targets.items
    assert idle.released == busy.released == [plane.id]


def test_remove_missing_target(manager: TargetManager) -> None:
    with pytest.raises(TargetNotFoundError):
        manager.remove_target("missing")
