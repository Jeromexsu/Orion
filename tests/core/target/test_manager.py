import pytest
from pydantic import ValidationError

from core.observation import Observation, ObservedPoint, observed_point
from core.target import (
    DuplicateTargetTypeError,
    Target,
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
from tests.core.target.fakes import InMemoryTargetRepository, Ship

# ---------------------------------------------------------------- 类型


def test_register_type_twice_rejected(target_types: TargetTypeRegistry) -> None:
    with pytest.raises(DuplicateTargetTypeError):
        target_types.register(Aircraft)


def test_observed_point_names_are_unique_within_a_type() -> None:
    class XObservation(Observation):
        x: float

    @observed_point("position", observation=XObservation)
    class OtherPosition(ObservedPoint): ...

    with pytest.raises(TypeError, match="'position'"):

        @target_type("car", observed_points=[Position, OtherPosition])
        class Car(Target): ...  # pyright: ignore[reportUnusedClass]

    # 不同类型里同名不冲突：观察点名只在本类型内解析
    @target_type("boat", observed_points=[OtherPosition])
    class Boat(Target): ...

    registry = TargetTypeRegistry()
    registry.register(Aircraft)
    registry.register(Boat)
    assert registry.types() == [Aircraft, Boat]


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


# ---------------------------------------------------------------- 删除


def test_remove_target(
    manager: TargetManager, plane: Target, targets: InMemoryTargetRepository
) -> None:
    manager.remove_target(plane.id)
    assert plane.id not in targets.items
    with pytest.raises(TargetNotFoundError):
        manager.remove_target(plane.id)
