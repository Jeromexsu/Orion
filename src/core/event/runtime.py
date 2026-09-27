from core.event.compiler import TemplateCompiler
from core.event.repository import EventRepository, RunnerStateRepository, TemplateRepository
from core.hooks import ProposalSink
from core.report import ReportManager
from core.target import TargetManager


class EventRuntime:
    """runner 和子事件共用的运行时依赖，bootstrap 时装配一次。

    只放它们真正用到的；只有父事件用到的依赖在 ParentEventServices 里。
    """

    def __init__(
        self,
        event_repository: EventRepository,
        runner_state_repository: RunnerStateRepository,
        proposal_sink: ProposalSink,
    ) -> None:
        self.event_repository = event_repository  # runner：存取子事件记录
        self.runner_state_repository = runner_state_repository  # runner：开启条件状态
        self.proposal_sink = proposal_sink  # 子事件：钩子提的提议


class ParentEventServices:
    """只有父事件用到的依赖，bootstrap 时装配一次。父事件记录的仓库在 ParentEventManager 里。"""

    def __init__(
        self,
        target_manager: TargetManager,
        template_repository: TemplateRepository,
        template_compiler: TemplateCompiler,
        report_manager: ReportManager,
    ) -> None:
        self.target_manager = target_manager  # 确认目标存在、取目标名
        self.template_repository = template_repository  # 模板定义
        self.template_compiler = template_compiler  # 编译模板
        self.report_manager = report_manager  # digest 写报告
