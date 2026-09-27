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
    """父事件、runner、子事件共用的运行时依赖，bootstrap 时装配一次。

    只有父事件用到的依赖（模板编译器）不放这里，由 ParentEventManager 单独交给父事件。
    """

    def __init__(
        self,
        targets: TargetManager,
        operator_registry: OperatorRegistry,
        suggestions: SuggestionSink,
        parents: ParentEventRepository,
        templates: TemplateRepository,
        events: EventRepository,
        runner_states: RunnerStateRepository,
        reports: ReportManager,
    ) -> None:
        self.targets = targets
        self.operator_registry = operator_registry
        self.suggestions = suggestions
        self.parents = parents
        self.templates = templates
        self.events = events
        self.runner_states = runner_states
        self.reports = reports
