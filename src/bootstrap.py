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
from core.condition_engine import ConditionCompiler, EvaluatorRegistry
from core.event import (
    EventRepository,
    EventRuntime,
    ParentEventManager,
    ParentEventRepository,
    ParentEventServices,
    RunnerStateRepository,
    TemplateCompiler,
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
        target_repository: TargetRepository,
        observable_target_repository: ObservableTargetRepository,
        cursor_repository: CursorRepository,
        observation_repository: ObservationRepository,
        parent_event_repository: ParentEventRepository,
        template_repository: TemplateRepository,
        event_repository: EventRepository,
        runner_state_repository: RunnerStateRepository,
        draft_repository: DraftRepository,
        suggestion_repository: SuggestionRepository,
    ) -> None:
        self.target_repository = target_repository
        self.observable_target_repository = observable_target_repository
        self.cursor_repository = cursor_repository
        self.observation_repository = observation_repository
        self.parent_event_repository = parent_event_repository
        self.template_repository = template_repository
        self.event_repository = event_repository
        self.runner_state_repository = runner_state_repository
        self.draft_repository = draft_repository
        self.suggestion_repository = suggestion_repository


class App:
    """装配好的核心对象。"""

    def __init__(
        self,
        target_manager: TargetManager,
        adapter_registry: AdapterRegistry,
        collector: Collector,
        condition_compiler: ConditionCompiler,
        operator_registry: OperatorRegistry,
        parent_event_manager: ParentEventManager,
        report_manager: ReportManager,
        hil_manager: HilManager,
    ) -> None:
        self.target_manager = target_manager
        self.adapter_registry = adapter_registry
        self.collector = collector
        self.condition_compiler = condition_compiler
        self.operator_registry = operator_registry
        self.parent_event_manager = parent_event_manager
        self.report_manager = report_manager
        self.hil_manager = hil_manager


def build_app(repos: Repositories) -> App:
    """装配并完成重启恢复。"""
    adapter_registry = AdapterRegistry()
    # 在这里 adapter_registry.register(...) 各上游 Adapter 插件

    target_manager = TargetManager(
        repos.target_repository, repos.observable_target_repository, adapter_registry
    )
    target_manager.register_type(Aircraft)

    collector = Collector(
        target_manager,
        adapter_registry,
        repos.cursor_repository,
        repos.observation_repository,
        Dispatcher(),
    )

    evaluator_registry = EvaluatorRegistry()
    evaluator_registry.register(OnEnter())
    condition_compiler = ConditionCompiler(evaluator_registry)

    report_manager = ReportManager(repos.draft_repository)
    hil_manager = HilManager(repos.suggestion_repository)

    operator_registry = OperatorRegistry()
    operator_registry.register(CountHits())
    operator_registry.register(CloseReport(report_manager))

    parent_event_manager = ParentEventManager(
        repos.parent_event_repository,
        ParentEventServices(
            target_manager=target_manager,
            template_repository=repos.template_repository,
            template_compiler=TemplateCompiler(
                condition_compiler, operator_registry, target_manager
            ),
            report_manager=report_manager,
        ),
        EventRuntime(
            event_repository=repos.event_repository,
            runner_state_repository=repos.runner_state_repository,
            operator_registry=operator_registry,
            suggestion_sink=hil_manager,
        ),
    )
    _allow_actions(hil_manager, parent_event_manager)

    # 所有插件注册完之后再恢复：模板重新编译要用到它们
    failed = parent_event_manager.restore()
    if failed:
        logger.error("failed to restore parent events: %s", failed)

    return App(
        target_manager=target_manager,
        adapter_registry=adapter_registry,
        collector=collector,
        condition_compiler=condition_compiler,
        operator_registry=operator_registry,
        parent_event_manager=parent_event_manager,
        report_manager=report_manager,
        hil_manager=hil_manager,
    )


def _allow_actions(hil_manager: HilManager, parent_event_manager: ParentEventManager) -> None:
    """hil 白名单：建议能触发的核心公开方法。proposal.target 是父事件 ID。"""

    def add_target(parent_id: str | None, args: dict[str, Any]) -> object:
        return parent_event_manager.get(_required(parent_id)).add_target(args["target_id"])

    def remove_target(parent_id: str | None, args: dict[str, Any]) -> object:
        return parent_event_manager.get(_required(parent_id)).remove_target(args["target_id"])

    def upsert_template(parent_id: str | None, args: dict[str, Any]) -> object:
        template_def = TemplateDef.model_validate(args["template_def"])
        return parent_event_manager.get(_required(parent_id)).upsert_template(template_def)

    hil_manager.allow("add_target", add_target)
    hil_manager.allow("remove_target", remove_target)
    hil_manager.allow("upsert_template", upsert_template)


def _required(parent_id: str | None) -> str:
    if parent_id is None:
        raise ValueError("proposal.target (parent event id) is required")
    return parent_id
