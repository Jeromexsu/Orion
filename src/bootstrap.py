"""唯一的跨切面装配点：把持久化实现注入 core，把插件注册进各 registry。

API 进程和异步 worker 进程共用这里的装配逻辑。
"""

import logging
from typing import Any

from core.collector import (
    AdapterRegistry,
    Collector,
    CursorRepository,
    Dispatcher,
    DynamicDataRepository,
)
from core.condition_engine import ConditionEngine, EvaluatorRegistry
from core.event import (
    EventManager,
    TemplateDef,
    EventRuntime,
    InstanceRepository,
    ParentEventRepository,
    TemplateRepository,
)
from core.hil import HilManager, SuggestionRepository
from core.operators import OperatorRegistry
from core.report import DraftRepository, ReportManager
from core.target import ObservableTargetRepository, TargetManager, TargetRepository
from plugins.condition_engine.on_enter import OnEnter
from plugins.operators.close_report import CloseReport
from plugins.operators.count_hits import CountHits
from plugins.target.aircraft import AircraftType

logger = logging.getLogger(__name__)


class Repositories:
    """持久化实现的集合。TODO: persistence 层就绪后在这里构造具体实现。"""

    def __init__(
        self,
        targets: TargetRepository,
        observables: ObservableTargetRepository,
        cursors: CursorRepository,
        dynamic_data: DynamicDataRepository,
        parents: ParentEventRepository,
        templates: TemplateRepository,
        instances: InstanceRepository,
        drafts: DraftRepository,
        suggestions: SuggestionRepository,
    ) -> None:
        self.targets = targets
        self.observables = observables
        self.cursors = cursors
        self.dynamic_data = dynamic_data
        self.parents = parents
        self.templates = templates
        self.instances = instances
        self.drafts = drafts
        self.suggestions = suggestions


class App:
    """装配好的核心对象。"""

    def __init__(
        self,
        targets: TargetManager,
        adapters: AdapterRegistry,
        collector: Collector,
        conditions: ConditionEngine,
        operators: OperatorRegistry,
        events: EventManager,
        reports: ReportManager,
        hil: HilManager,
    ) -> None:
        self.targets = targets
        self.adapters = adapters
        self.collector = collector
        self.conditions = conditions
        self.operators = operators
        self.events = events
        self.reports = reports
        self.hil = hil


def build_app(repos: Repositories) -> App:
    """装配并完成重启恢复。"""
    adapters = AdapterRegistry()
    # 在这里 adapters.register(...) 各上游 Adapter 插件

    targets = TargetManager(repos.targets, repos.observables, adapters)
    targets.register_type(AircraftType())

    collector = Collector(targets, adapters, repos.cursors, repos.dynamic_data, Dispatcher())

    evaluators = EvaluatorRegistry()
    evaluators.register(OnEnter())
    conditions = ConditionEngine(evaluators, resolver=targets)

    reports = ReportManager(repos.drafts)
    hil = HilManager(repos.suggestions)

    operators = OperatorRegistry()
    operators.register(CountHits())
    operators.register(CloseReport(reports))

    events = EventManager(
        EventRuntime(
            targets=targets,
            conditions=conditions,
            operators=operators,
            suggestions=hil,
            parents=repos.parents,
            templates=repos.templates,
            instances=repos.instances,
            reports=reports,
        )
    )
    _allow_actions(hil, events)

    # 所有插件注册完之后再恢复：模板重新编译要用到它们
    failed = events.restore()
    if failed:
        logger.error("failed to restore parent events: %s", failed)

    return App(
        targets=targets,
        adapters=adapters,
        collector=collector,
        conditions=conditions,
        operators=operators,
        events=events,
        reports=reports,
        hil=hil,
    )


def _allow_actions(hil: HilManager, events: EventManager) -> None:
    """hil 白名单：建议能触发的核心公开方法。proposal.target 是父事件 ID。"""

    def add_target(parent_id: str | None, args: dict[str, Any]) -> object:
        return events.get(_required(parent_id)).add_target(args["target_id"], args["focus"])

    def remove_target(parent_id: str | None, args: dict[str, Any]) -> object:
        return events.get(_required(parent_id)).remove_target(args["observable_id"])

    def upsert_template(parent_id: str | None, args: dict[str, Any]) -> object:
        definition = TemplateDef.model_validate(args["definition"])
        return events.get(_required(parent_id)).upsert_template(definition)

    hil.allow("add_target", add_target)
    hil.allow("remove_target", remove_target)
    hil.allow("upsert_template", upsert_template)


def _required(parent_id: str | None) -> str:
    if parent_id is None:
        raise ValueError("proposal.target (parent event id) is required")
    return parent_id
