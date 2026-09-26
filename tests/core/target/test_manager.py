import pytest
from pydantic import ValidationError

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
)
from plugins.target.aircraft import AircraftPosition, AircraftType
from tests.core.target.conftest import Subscriber
from tests.core.target.fakes import InMemoryObservableTargetRepository, InMemoryTargetRepository


def test_register_type_twice_rejected(manager: TargetManager) -> None:
    with pytest.raises(DuplicateTargetTypeError):
        manager.register_type(AircraftType())


def test_upsert_target_validates_and_normalizes_attributes(
    manager: TargetManager, targets: InMemoryTargetRepository
) -> None:
    saved = manager.upsert_target(
        Target(id="t1", type="aircraft", name="x", attributes={"registration": "B-1"})
    )
    assert saved.attributes == {"registration": "B-1", "icao24": None}
    assert targets.items["t1"] == saved


def test_upsert_target_rejects_bad_attributes(manager: TargetManager) -> None:
    with pytest.raises(ValidationError):
        manager.upsert_target(Target(id="t1", type="aircraft", name="x", attributes={}))


def test_upsert_target_unknown_type(manager: TargetManager) -> None:
    with pytest.raises(UnknownTargetTypeError):
        manager.upsert_target(Target(id="t1", type="ship", name="x"))


def test_upsert_target_cannot_change_type(manager: TargetManager, plane: Target) -> None:
    class ShipType:
        name = "ship"
        attributes_model = AircraftPosition
        focuses = {}

    manager.register_type(ShipType())
    with pytest.raises(TargetTypeChangeError):
        manager.upsert_target(plane.model_copy(update={"type": "ship"}))


def test_find_by_alias(manager: TargetManager, plane: Target) -> None:
    assert manager.find_by_alias("MU5101") == plane
    assert manager.find_by_alias("nope") is None


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
    from tests.core.target.fakes import StaticUpstreamCatalog

    m = TargetManager(
        InMemoryTargetRepository(), InMemoryObservableTargetRepository(), StaticUpstreamCatalog({})
    )
    m.register_type(AircraftType())
    m.upsert_target(Target(id="t1", type="aircraft", name="x", attributes={"registration": "B"}))
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
    manager.upsert_target(plane.model_copy(update={"attributes": {"registration": "B-9999"}}))
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
