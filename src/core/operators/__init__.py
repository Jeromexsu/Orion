"""算子：挂在子事件生命周期上的可插拔动作。

负责：算子基类与声明（@operator）；注册；按声明组装的上下文（能力没声明就用不了）；调用时机（Occasion）。
      算子何时被调用、挂载是否合法由 event 决定，这里不调度、不校验挂载。
两个正交的维度：直接作用于哪些作用域（external / event），能否提建议（经 hil 审核；parent / target 只能走这条）。
对外：Operator、operator、OperatorContext、EventHandle、Occasion 及各挂载点的时机类型、OperatorRegistry、
      SuggestionSink（建议的去处，由 hil 实现）。
依赖：target（ObservationEnvelope）、condition_engine（EvalResult）、hil（Suggestion）。
扩展点：plugins/operators/ 下继承 Operator[参数模型]，用 @operator 声明。
"""

from core.operators.context import EventHandle, OperatorContext
from core.operators.errors import (
    DuplicateOperatorError,
    OperatorError,
    UndeclaredCapabilityError,
    UnknownOperatorError,
)
from core.operators.occasion import (
    ClosedOccasion,
    CreatedOccasion,
    ObservationOccasion,
    Occasion,
    RuleHitOccasion,
    StatusUpdatedOccasion,
)
from core.operators.operator import (
    DIRECT_SCOPES,
    MountPoint,
    NoParams,
    Operator,
    Scope,
    operator,
)
from core.operators.registry import OperatorRegistry
from core.operators.sink import SuggestionSink

__all__ = [
    "DIRECT_SCOPES",
    "ClosedOccasion",
    "CreatedOccasion",
    "DuplicateOperatorError",
    "EventHandle",
    "MountPoint",
    "NoParams",
    "ObservationOccasion",
    "Occasion",
    "Operator",
    "OperatorContext",
    "OperatorError",
    "OperatorRegistry",
    "RuleHitOccasion",
    "Scope",
    "StatusUpdatedOccasion",
    "SuggestionSink",
    "UndeclaredCapabilityError",
    "UnknownOperatorError",
    "operator",
]
