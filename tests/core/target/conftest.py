import pytest

from core.target import ObservationEnvelope, Target, TargetManager
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
def manager(
    targets: InMemoryTargetRepository, observables: InMemoryObservableTargetRepository
) -> TargetManager:
    upstreams = StaticUpstreamCatalog({("aircraft", "position"): ["adsb"]})
    m = TargetManager(targets, observables, upstreams)
    m.register_type(Aircraft)
    return m


@pytest.fixture
def plane(manager: TargetManager) -> Target:
    return manager.upsert_target(
        Aircraft(id="t1", name="东航 MU5101", registration="B-2447", aliases=["MU5101"])
    )
