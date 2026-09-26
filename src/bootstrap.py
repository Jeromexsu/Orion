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
    ObservationRepository,
)
from core.condition_engine import ConditionEngine, EvaluatorRegistry
from core.event import (
    EventRepository,
    EventRuntime,
    ParentEventManager,
    ParentEventRepository,
    RunnerStateRepository,
    TemplateDef,
    TemplateRepository,
)
from core.hil import HilManager, SuggestionRepository
from core.operators import OperatorRegistry
from core.report import DraftRepository, ReportManager
from core.target import ObservableTargetRepository, TargetManager, TargetRepository
from plugins.condition_engine.on_enter import OnEnter
from plugins.operators.close_report import CloseReport
from plugins.operators.count_hits import CountHits
from plugins.target.aircraft import Aircraft

logger = logging.getLogger(__name__)


class Repositories:
    """持久化实现的集合。TODO: persistence 层就绪后在这里构造具体实现。"""

    def __init__(
        self,
        targets: TargetRepository,
        observables: ObservableTargetRepository,
        cursors: CursorRepository,
        observations: ObservationRepository,
        parents: ParentEventRepository,
        templates: TemplateRepository,
        events: EventRepository,
        runner_states: RunnerStateRepository,
        drafts: DraftRepository,
        suggestions: SuggestionRepository,
    ) -> None:
        self.targets = targets
        self.observables = observables
        self.cursors = cursors
        self.observations = observations
        self.parents = parents
        self.templates = templates
        self.events = events
        self.runner_states = runner_states
        self.drafts = drafts
        self.suggestions = suggestions


class App:
    """装配好的核心对象。"""

    def __init__(
        self,
        targets: TargetManager,
        adapter_registry: AdapterRegistry,
        collector: Collector,
        conditions: ConditionEngine,
        operator_registry: OperatorRegistry,
        parent_events: ParentEventManager,
        reports: ReportManager,
        hil: HilManager,
    ) -> None:
        self.targets = targets
        self.adapter_registry = adapter_registry
        self.collector = collector
        self.conditions = conditions
        self.operator_registry = operator_registry
        self.parent_events = parent_events
        self.reports = reports
        self.hil = hil


def build_app(repos: Repositories) -> App:
    """装配并完成重启恢复。"""
    adapter_registry = AdapterRegistry()
    # 在这里 adapter_registry.register(...) 各上游 Adapter 插件

    targets = TargetManager(repos.targets, repos.observables, adapter_registry)
    targets.register_type(Aircraft)

    collector = Collector(
        targets, adapter_registry, repos.cursors, repos.observations, Dispatcher()
    )

    evaluator_registry = EvaluatorRegistry()
    evaluator_registry.register(OnEnter())
    conditions = ConditionEngine(evaluator_registry)

    reports = ReportManager(repos.drafts)
    hil = HilManager(repos.suggestions)

    operator_registry = OperatorRegistry()
    operator_registry.register(CountHits())
    operator_registry.register(CloseReport(reports))

    parent_events = ParentEventManager(
        EventRuntime(
            targets=targets,
            conditions=conditions,
            operator_registry=operator_registry,
            suggestions=hil,
            parents=repos.parents,
            templates=repos.templates,
            events=repos.events,
            runner_states=repos.runner_states,
            reports=reports,
        )
    )
    _allow_actions(hil, parent_events)

    # 所有插件注册完之后再恢复：模板重新编译要用到它们
    failed = parent_events.restore()
    if failed:
        logger.error("failed to restore parent events: %s", failed)

    return App(
        targets=targets,
        adapter_registry=adapter_registry,
        collector=collector,
        conditions=conditions,
        operator_registry=operator_registry,
        parent_events=parent_events,
        reports=reports,
        hil=hil,
    )


def _allow_actions(hil: HilManager, parent_events: ParentEventManager) -> None:
    """hil 白名单：建议能触发的核心公开方法。proposal.target 是父事件 ID。"""

    def add_target(parent_id: str | None, args: dict[str, Any]) -> object:
        return parent_events.get(_required(parent_id)).add_target(args["target_id"])

    def remove_target(parent_id: str | None, args: dict[str, Any]) -> object:
        return parent_events.get(_required(parent_id)).remove_target(args["target_id"])

    def upsert_template(parent_id: str | None, args: dict[str, Any]) -> object:
        template_def = TemplateDef.model_validate(args["template_def"])
        return parent_events.get(_required(parent_id)).upsert_template(template_def)

    hil.allow("add_target", add_target)
    hil.allow("remove_target", remove_target)
    hil.allow("upsert_template", upsert_template)


def _required(parent_id: str | None) -> str:
    if parent_id is None:
        raise ValueError("proposal.target (parent event id) is required")
    return parent_id
