"""唯一的跨切面装配点：把持久化实现注入 core，把插件注册进各 registry。

API 进程和异步 worker 进程共用这里的装配逻辑。
"""

from core.collector import (
    AdapterRegistry,
    Collector,
    CursorRepository,
    Dispatcher,
    DynamicDataRepository,
)
from core.condition_engine import ConditionEngine, EvaluatorRegistry
from core.target import ObservableTargetRepository, TargetManager, TargetRepository
from plugins.condition_engine.on_enter import OnEnter
from plugins.target.aircraft import AircraftType


class Repositories:
    """持久化实现的集合。TODO: persistence 层就绪后在这里构造具体实现。"""

    def __init__(
        self,
        targets: TargetRepository,
        observables: ObservableTargetRepository,
        cursors: CursorRepository,
        dynamic_data: DynamicDataRepository,
    ) -> None:
        self.targets = targets
        self.observables = observables
        self.cursors = cursors
        self.dynamic_data = dynamic_data


class App:
    """装配好的核心对象。"""

    def __init__(
        self,
        targets: TargetManager,
        adapters: AdapterRegistry,
        collector: Collector,
        conditions: ConditionEngine,
    ) -> None:
        self.targets = targets
        self.adapters = adapters
        self.collector = collector
        self.conditions = conditions


def build_app(repos: Repositories) -> App:
    adapters = AdapterRegistry()
    # 在这里 adapters.register(...) 各上游 Adapter 插件

    targets = TargetManager(repos.targets, repos.observables, adapters)
    targets.register_type(AircraftType())

    collector = Collector(targets, adapters, repos.cursors, repos.dynamic_data, Dispatcher())

    evaluators = EvaluatorRegistry()
    evaluators.register(OnEnter())
    conditions = ConditionEngine(evaluators, resolver=targets)

    return App(targets=targets, adapters=adapters, collector=collector, conditions=conditions)
