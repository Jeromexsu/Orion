"""唯一的跨切面装配点：把持久化实现注入 core，把插件注册进各 registry。

API 进程和异步 worker 进程共用这里的装配逻辑。
"""

import logging

from pydantic import BaseModel, ConfigDict

from core.collector import (
    Collector,
    CursorRepository,
    ObservationRepository,
    UpstreamAdapterRegistry,
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
from core.hil import HilManager, ProposalRepository
from core.hooks import HookRegistry, MountCompiler
from core.report import DraftRepository, ReportManager
from core.target import ObservableTargetRepository, TargetManager, TargetRepository
from plugins.condition_engine.on_enter import OnEnter
from plugins.hooks.close_report import CloseReport
from plugins.hooks.count_hits import CountHits
from plugins.target.aircraft import Aircraft
from plugins.upstream_adapters.opensky import OpenSkyAdapter

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
        proposal_repository: ProposalRepository,
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
        self.proposal_repository = proposal_repository


class App:
    """装配好的核心对象。"""

    def __init__(
        self,
        target_manager: TargetManager,
        upstream_adapter_registry: UpstreamAdapterRegistry,
        collector: Collector,
        condition_compiler: ConditionCompiler,
        hook_registry: HookRegistry,
        parent_event_manager: ParentEventManager,
        report_manager: ReportManager,
        hil_manager: HilManager,
    ) -> None:
        self.target_manager = target_manager
        self.upstream_adapter_registry = upstream_adapter_registry
        self.collector = collector
        self.condition_compiler = condition_compiler
        self.hook_registry = hook_registry
        self.parent_event_manager = parent_event_manager
        self.report_manager = report_manager
        self.hil_manager = hil_manager


def build_app(repos: Repositories) -> App:
    """装配并完成重启恢复。"""
    upstream_adapter_registry = UpstreamAdapterRegistry()
    upstream_adapter_registry.register(OpenSkyAdapter())

    target_manager = TargetManager(
        repos.target_repository, repos.observable_target_repository, upstream_adapter_registry
    )
    target_manager.register_type(Aircraft)

    collector = Collector(
        target_manager,
        upstream_adapter_registry,
        repos.cursor_repository,
        repos.observation_repository,
    )

    evaluator_registry = EvaluatorRegistry()
    evaluator_registry.register(OnEnter())
    condition_compiler = ConditionCompiler(evaluator_registry)

    report_manager = ReportManager(repos.draft_repository)
    hil_manager = HilManager(repos.proposal_repository)

    hook_registry = HookRegistry()
    hook_registry.register(CountHits())
    hook_registry.register(CloseReport(report_manager))

    parent_event_manager = ParentEventManager(
        repos.parent_event_repository,
        ParentEventServices(
            target_manager=target_manager,
            template_repository=repos.template_repository,
            template_compiler=TemplateCompiler(
                condition_compiler, MountCompiler(hook_registry), target_manager
            ),
            report_manager=report_manager,
        ),
        EventRuntime(
            event_repository=repos.event_repository,
            runner_state_repository=repos.runner_state_repository,
            proposal_sink=hil_manager,
        ),
    )
    _allow_actions(hil_manager, parent_event_manager)

    # 所有插件注册完之后再恢复：模板重新编译要用到它们
    failed = parent_event_manager.restore()
    if failed:
        logger.error("failed to restore parent events: %s", failed)

    return App(
        target_manager=target_manager,
        upstream_adapter_registry=upstream_adapter_registry,
        collector=collector,
        condition_compiler=condition_compiler,
        hook_registry=hook_registry,
        parent_event_manager=parent_event_manager,
        report_manager=report_manager,
        hil_manager=hil_manager,
    )


class TargetActionArgs(BaseModel):
    """Arguments of add_target / remove_target."""

    model_config = ConfigDict(frozen=True)

    parent_id: str
    target_id: str


class TemplateActionArgs(BaseModel):
    """Arguments of upsert_template."""

    model_config = ConfigDict(frozen=True)

    parent_id: str
    template_def: TemplateDef


def _allow_actions(hil_manager: HilManager, parent_event_manager: ParentEventManager) -> None:
    """Whitelist the core public methods proposals can trigger, each with its args model."""

    def add_target(args: TargetActionArgs) -> object:
        return parent_event_manager.get(args.parent_id).add_target(args.target_id)

    def remove_target(args: TargetActionArgs) -> object:
        return parent_event_manager.get(args.parent_id).remove_target(args.target_id)

    def upsert_template(args: TemplateActionArgs) -> object:
        return parent_event_manager.get(args.parent_id).upsert_template(args.template_def)

    hil_manager.allow("add_target", TargetActionArgs, add_target)
    hil_manager.allow("remove_target", TargetActionArgs, remove_target)
    hil_manager.allow("upsert_template", TemplateActionArgs, upsert_template)
