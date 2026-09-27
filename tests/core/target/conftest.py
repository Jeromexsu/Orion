import pytest

from core.target import ObservationEnvelope, Target, TargetManager, TargetTypeRegistry
from plugins.target.aircraft import Aircraft
from tests.core.target.fakes import (
    InMemoryObservableTargetRepository,
    InMemoryTargetRepository,
    StaticUpstreamCatalog,
)


class Subscriber:
    def __init__(self) -> None:
        self.received: list[ObservationEnvelope] = []

    def on_observation(self, envelope: ObservationEnvelope) -> None:
        self.received.append(envelope)


@pytest.fixture
def targets() -> InMemoryTargetRepository:
    return InMemoryTargetRepository()


@pytest.fixture
def observables() -> InMemoryObservableTargetRepository:
    return InMemoryObservableTargetRepository()


@pytest.fixture
def target_types() -> TargetTypeRegistry:
    registry = TargetTypeRegistry()
    registry.register(Aircraft)
    return registry


@pytest.fixture
def manager(
    target_types: TargetTypeRegistry,
    targets: InMemoryTargetRepository,
    observables: InMemoryObservableTargetRepository,
) -> TargetManager:
    upstreams = StaticUpstreamCatalog({("aircraft", "position"): ["adsb"]})
    return TargetManager(target_types, targets, observables, upstreams)


@pytest.fixture
def plane(manager: TargetManager) -> Target:
    return manager.upsert_target(
        Aircraft(id="t1", name="东航 MU5101", registration="B-2447", aliases=["MU5101"])
    )
