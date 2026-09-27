"""事件：把观测变成有生命周期的子事件，驱动钩子和报告。

负责：
- 父事件（ParentEvent）：静态的目标命名空间 + 模板集合 + 汇总报告；自己不订阅；
- 模板：TemplateDef --TemplateCompiler--> EventTemplate（不可变、带版本）；
- 运行：每个模板一个 EventRunner，订阅可观测目标、评估开启条件、管理子事件（Event，同一模板最多一个活跃）。
对外：ParentEventManager 是入口；TemplateDef 等定义是纯数据（前端 / API 构造）；
      ParentEventServices / EventRuntime 是 bootstrap 装配的依赖包。
依赖：target、condition_engine、hooks、report（不直接依赖 collector / hil，分别经订阅回调和 ProposalSink 连接）。
关系图见 README「架构」一节。
"""

from core.event.compiler import TemplateCompiler
from core.event.definitions import ObservableDef, RuleDef, TemplateDef
from core.event.errors import (
    DuplicateParentEventError,
    EventClosedError,
    EventError,
    ParentEventNotFoundError,
    TargetStillReferencedError,
    TemplateCompileError,
    TemplateNotFoundError,
    TemplateScopeError,
    TemplateVersionError,
)
from core.event.event import Event
from core.event.manager import ParentEventManager
from core.event.parent import ParentEvent
from core.event.records import EventRecord, ParentEventRecord, TemplateRef
from core.event.repository import (
    EventRepository,
    ParentEventRepository,
    RunnerStateRepository,
    TemplateRepository,
)
from core.event.runner import EventRunner
from core.event.runtime import EventRuntime, ParentEventServices
from core.event.template import CompiledObservable, CompiledRule, EventTemplate

__all__ = [
    "CompiledObservable",
    "CompiledRule",
    "DuplicateParentEventError",
    "EventError",
    "ParentEventManager",
    "EventRuntime",
    "EventClosedError",
    "EventRecord",
    "EventRepository",
    "ObservableDef",
    "ParentEvent",
    "ParentEventNotFoundError",
    "ParentEventRecord",
    "ParentEventRepository",
    "ParentEventServices",
    "RuleDef",
    "RunnerStateRepository",
    "Event",
    "EventRunner",
    "EventTemplate",
    "TargetStillReferencedError",
    "TemplateCompileError",
    "TemplateDef",
    "TemplateCompiler",
    "TemplateNotFoundError",
    "TemplateRef",
    "TemplateRepository",
    "TemplateScopeError",
    "TemplateVersionError",
]
