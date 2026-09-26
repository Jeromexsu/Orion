from collections.abc import Mapping
from typing import ClassVar, Literal

import pytest
from pydantic import BaseModel, ValidationError

from core.target import (
    DuplicateTargetTypeError,
    NoUpstreamError,
    Target,
    TargetInUseError,
    TargetManager,
    TargetNotFoundError,
    TargetTypeChangeError,
    UnknownTargetTypeError,
    UnsupportedFocusError,
    type_name,
)
from plugins.target.aircraft import Aircraft, AircraftPosition
from tests.core.target.conftest import Subscriber
from tests.core.target.fakes import (
    InMemoryObservableTargetRepository,
    InMemoryTargetRepository,
    StaticUpstreamCatalog,
)


class Ship(Target, frozen=True):
    focuses: ClassVar[Mapping[str, type[BaseModel]]] = {}
    type: Literal["ship"] = "ship"
    mmsi: str


# ---------------------------------------------------------------- 类型


def test_register_type_twice_rejected(manager: TargetManager) -> None:
    with pytest.raises(DuplicateTargetTypeError):
        manager.register_type(Aircraft)


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


def test_get_observable_errors(manager: TargetManager, plane: Target) -> None:
    with pytest.raises(TargetNotFoundError):
        manager.get_observable("missing", "position")
    with pytest.raises(UnsupportedFocusError):
        manager.get_observable(plane.id, "fuel")


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
    obs.acquire(sub)
    assert manager.active_observables() == [obs]

    obs.release(sub)
    assert manager.active_observables() == []


def test_upsert_target_rebinds_live_observable(manager: TargetManager, plane: Target) -> None:
    obs = manager.get_observable(plane.id, "position")
    manager.upsert_target(plane.model_copy(update={"registration": "B-9999"}))
    assert obs.query_spec().attributes["registration"] == "B-9999"


def test_remove_target_in_use_rejected(manager: TargetManager, plane: Target) -> None:
    obs = manager.get_observable(plane.id, "position")
    obs.acquire(Subscriber())
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


def test_dynamic_schema_resolves_without_live_observable(
    manager: TargetManager, plane: Target
) -> None:
    assert manager.dynamic_schema("t1:position") is AircraftPosition
    assert manager.dynamic_schema("t1:fuel") is None
    assert manager.dynamic_schema("missing:position") is None
    assert manager.dynamic_schema("no-separator") is None
