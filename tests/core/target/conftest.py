import pytest

from core.target import Target, TargetManager, TargetTypeRegistry
from plugins.target.aircraft import Aircraft
from tests.core.target.fakes import InMemoryTargetRepository


@pytest.fixture
def targets() -> InMemoryTargetRepository:
    return InMemoryTargetRepository()


@pytest.fixture
def target_types() -> TargetTypeRegistry:
    registry = TargetTypeRegistry()
    registry.register(Aircraft)
    return registry


@pytest.fixture
def manager(target_types: TargetTypeRegistry, targets: InMemoryTargetRepository) -> TargetManager:
    return TargetManager(target_types, targets)


@pytest.fixture
def plane(manager: TargetManager) -> Target:
    return manager.upsert_target(
        Aircraft(id="t1", name="东航 MU5101", registration="B-2447", aliases=["MU5101"])
    )
