"""唯一的跨切面装配点：把持久化实现注入 core，把插件注册进各 registry。

API 进程和异步 worker 进程共用这里的装配逻辑。
"""

from core.target import ObservableTargetRepository, TargetManager, TargetRepository, UpstreamCatalog
from plugins.target.aircraft import AircraftType


def build_target_manager(
    targets: TargetRepository,
    observables: ObservableTargetRepository,
    upstreams: UpstreamCatalog,
) -> TargetManager:
    # TODO: persistence 层就绪后在这里构造仓库实现；upstreams 由 collector 的 AdapterRegistry 提供
    manager = TargetManager(targets, observables, upstreams)
    manager.register_type(AircraftType())
    return manager
