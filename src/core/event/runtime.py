from core.event.compiler import TemplateCompiler
from core.event.repository import (
    EventRepository,
    ParentEventRepository,
    RunnerStateRepository,
    TemplateRepository,
)
from core.operators import OperatorRegistry, SuggestionSink
from core.report import ReportManager
from core.target import TargetManager


class EventRuntime:
    """runner 和子事件共用的运行时依赖，bootstrap 时装配一次。

    只放它们真正用到的；只有父事件用到的依赖在 ParentEventServices 里。
    """

    def __init__(
        self,
        events: EventRepository,
        runner_states: RunnerStateRepository,
        operator_registry: OperatorRegistry,
        suggestions: SuggestionSink,
    ) -> None:
        self.events = events                        # runner：存取子事件记录
        self.runner_states = runner_states          # runner：开启条件状态
        self.operator_registry = operator_registry  # 子事件：跑算子
        self.suggestions = suggestions              # 子事件：算子提的建议


class ParentEventServices:
    """只有父事件（及其管理器）用到的依赖，bootstrap 时装配一次。"""

    def __init__(
        self,
        targets: TargetManager,
        parents: ParentEventRepository,
        templates: TemplateRepository,
        template_compiler: TemplateCompiler,
        reports: ReportManager,
    ) -> None:
        self.targets = targets                      # 确认目标存在、取目标名
        self.parents = parents                      # 父事件记录
        self.templates = templates                  # 模板定义
        self.template_compiler = template_compiler  # 编译模板
        self.reports = reports                      # digest 写报告
