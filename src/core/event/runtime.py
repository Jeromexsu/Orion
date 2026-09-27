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
    """event 活对象共用的运行时依赖，bootstrap 时装配一次。"""

    def __init__(
        self,
        targets: TargetManager,
        template_compiler: TemplateCompiler,
        operator_registry: OperatorRegistry,
        suggestions: SuggestionSink,
        parents: ParentEventRepository,
        templates: TemplateRepository,
        events: EventRepository,
        runner_states: RunnerStateRepository,
        reports: ReportManager,
    ) -> None:
        self.targets = targets
        self.template_compiler = template_compiler
        self.operator_registry = operator_registry
        self.suggestions = suggestions
        self.parents = parents
        self.templates = templates
        self.events = events
        self.runner_states = runner_states
        self.reports = reports
