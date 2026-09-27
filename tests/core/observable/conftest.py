import pytest

from core.observable import ObservableTargetManager
from core.target import TargetManager, TargetTypeRegistry
from tests.core.observable.fakes import InMemoryObservableTargetRepository, StaticUpstreamCatalog
from tests.core.target.conftest import manager, plane, target_types, targets

__all__ = ["manager", "plane", "target_types", "targets"]   # 复用 target 的夹具


@pytest.fixture
def observables() -> InMemoryObservableTargetRepository:
    return InMemoryObservableTargetRepository()


@pytest.fixture
def observable_manager(
    target_types: TargetTypeRegistry,
    manager: TargetManager,
    observables: InMemoryObservableTargetRepository,
) -> ObservableTargetManager:
    upstreams = StaticUpstreamCatalog({("aircraft", "position"): ["adsb"]})
    return ObservableTargetManager(target_types, manager, observables, upstreams)
