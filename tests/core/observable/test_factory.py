import pytest

from core.observable import (
    ObservableTargetFactory,
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
from tests.core.observable.fakes import Subscriber
from tests.core.target.fakes import InMemoryTargetRepository, Ship


def make(*types: type[Target]) -> tuple[TargetManager, ObservableTargetFactory]:
    target_types = TargetTypeRegistry()
    for t in types:
        target_types.register(t)
    targets = TargetManager(target_types, InMemoryTargetRepository())
    return targets, ObservableTargetFactory(targets)


def test_get_observable_is_singleton(
    observable_factory: ObservableTargetFactory, plane: Target
) -> None:
    a = observable_factory.get_observable(plane.id, "position")
    b = observable_factory.get_observable(plane.id, "position")
    assert a is b
    assert a.id == "t1:position"
    assert a.target_id == plane.id
    assert observable_factory.observables() == [a]


def test_get_observable_errors(
    observable_factory: ObservableTargetFactory, target_types: TargetTypeRegistry, plane: Target
) -> None:
    with pytest.raises(TargetNotFoundError):
        observable_factory.get_observable("missing", "position")
    with pytest.raises(UnsupportedObservedPointError):     # 飞机没有这个观察点
        observable_factory.get_observable(plane.id, "fuel")
    target_types.register(Ship)
    with pytest.raises(UnsupportedObservedPointError):  # 吃水是船的观察点，飞机不能被这样观测
        observable_factory.get_observable(plane.id, "draught")


def test_shared_observed_point_across_types() -> None:
    targets, observables = make(Aircraft, Ship)
    targets.upsert_target(Aircraft(id="a1", name="x", registration="B-1"))
    targets.upsert_target(Ship(id="s1", name="y", mmsi="412000000"))

    plane = observables.get_observable("a1", "position")
    ship = observables.get_observable("s1", "position")
    assert plane.observed_point is ship.observed_point is Position
    assert plane is not ship


def test_active_observables_follow_subscribers(
    observable_factory: ObservableTargetFactory, plane: Target
) -> None:
    obs = observable_factory.get_observable(plane.id, "position")
    assert observable_factory.active_observables() == []

    sub = Subscriber()
    obs.subscribe(sub, ["adsb"])
    assert observable_factory.active_observables() == [obs]

    obs.unsubscribe(sub)
    assert observable_factory.active_observables() == []


def test_observable_reads_the_current_target(
    manager: TargetManager, observable_factory: ObservableTargetFactory, plane: Target
) -> None:
    """可观测目标只存目标 ID：目标更新后，经它读到的就是新目标，不需要通知。"""
    obs = observable_factory.get_observable(plane.id, "position")
    manager.upsert_target(plane.model_copy(update={"registration": "B-9999"}))
    assert manager.get_target(obs.target_id).query_values() == {Registration: "B-9999"}
