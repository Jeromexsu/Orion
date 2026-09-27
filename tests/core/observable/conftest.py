import pytest

from core.observable import ObservableTargetFactory
from core.target import TargetManager
from tests.core.observable.fakes import StaticUpstreamCatalog
from tests.core.target.conftest import manager, plane, target_types, targets

__all__ = ["manager", "plane", "target_types", "targets"]   # 复用 target 的夹具


@pytest.fixture
def observable_factory(manager: TargetManager) -> ObservableTargetFactory:
    upstreams = StaticUpstreamCatalog({("aircraft", "position"): ["adsb"]})
    return ObservableTargetFactory(manager, upstreams)
