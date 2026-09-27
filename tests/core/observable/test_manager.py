import pytest

from core.observable import (
    NoUpstreamError,
    ObservableTargetManager,
    UnsupportedObservedPointError,
)
from core.target import (
    Target,
    TargetManager,
    TargetNotFoundError,
    TargetTypeRegistry,
)
from plugins.observed_points.position import Position
from plugins.query_keys.registration import Registration
from plugins.target.aircraft import Aircraft
from tests.core.observable.fakes import (
    InMemoryObservableTargetRepository,
    StaticUpstreamCatalog,
    Subscriber,
)
from tests.core.target.fakes import InMemoryTargetRepository, Ship


def make(
    table: dict[tuple[str, str], list[str]], *types: type[Target]
) -> tuple[TargetManager, ObservableTargetManager]:
    target_types = TargetTypeRegistry()
    for t in types:
        target_types.register(t)
    targets = TargetManager(target_types, InMemoryTargetRepository())
    observables = ObservableTargetManager(
        targets, InMemoryObservableTargetRepository(), StaticUpstreamCatalog(table)
    )
    return targets, observables


def test_get_observable_is_singleton(
    observable_manager: ObservableTargetManager,
    plane: Target,
    observables: InMemoryObservableTargetRepository,
) -> None:
    a = observable_manager.get_observable(plane.id, "position")
    b = observable_manager.get_observable(plane.id, "position")
    assert a is b
    assert a.id == "t1:position"
    assert a.target_id == plane.id
    assert observables.items[a.id] is a


def test_inspect_observable_does_not_create(
    observable_manager: ObservableTargetManager,
    plane: Target,
    observables: InMemoryObservableTargetRepository,
) -> None:
    point, upstreams = observable_manager.inspect_observable(plane.id, "position")
    assert (point, upstreams) == (Position, ("adsb",))
    assert observables.items == {}
    with pytest.raises(UnsupportedObservedPointError):
        observable_manager.inspect_observable(plane.id, "fuel")


def test_get_observable_errors(
    observable_manager: ObservableTargetManager, target_types: TargetTypeRegistry, plane: Target
) -> None:
    with pytest.raises(TargetNotFoundError):
        observable_manager.get_observable("missing", "position")
    with pytest.raises(UnsupportedObservedPointError):     # 没有哪种类型有这个观察点
        observable_manager.get_observable(plane.id, "fuel")
    target_types.register(Ship)
    with pytest.raises(UnsupportedObservedPointError):  # 吃水是船的观察点，飞机不能被这样观测
        observable_manager.get_observable(plane.id, "draught")


def test_get_observable_without_upstream() -> None:
    targets, observables = make({}, Aircraft)
    targets.upsert_target(Aircraft(id="t1", name="x", registration="B"))
    with pytest.raises(NoUpstreamError):
        observables.get_observable("t1", "position")


def test_shared_observed_point_across_types() -> None:
    targets, observables = make(
        {("aircraft", "position"): ["adsb"], ("ship", "position"): ["ais"]}, Aircraft, Ship
    )
    targets.upsert_target(Aircraft(id="a1", name="x", registration="B-1"))
    targets.upsert_target(Ship(id="s1", name="y", mmsi="412000000"))

    plane = observables.get_observable("a1", "position")
    ship = observables.get_observable("s1", "position")
    assert plane.observed_point is ship.observed_point is Position
    assert observables.inspect_observable("a1", "position")[1] == ("adsb",)
    assert observables.inspect_observable("s1", "position")[1] == ("ais",)


def test_active_observables_follow_subscribers(
    observable_manager: ObservableTargetManager, plane: Target
) -> None:
    obs = observable_manager.get_observable(plane.id, "position")
    assert observable_manager.active_observables() == []

    sub = Subscriber()
    obs.subscribe(sub, ["adsb"])
    assert observable_manager.active_observables() == [obs]

    obs.unsubscribe(sub)
    assert observable_manager.active_observables() == []


def test_observable_reads_the_current_target(
    manager: TargetManager, observable_manager: ObservableTargetManager, plane: Target
) -> None:
    """可观测目标只存目标 ID：目标更新后，经它读到的就是新目标，不需要通知。"""
    obs = observable_manager.get_observable(plane.id, "position")
    manager.upsert_target(plane.model_copy(update={"registration": "B-9999"}))
    assert manager.get_target(obs.target_id).query_values() == {Registration: "B-9999"}
