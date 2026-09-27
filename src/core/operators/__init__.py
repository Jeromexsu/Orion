"""算子：挂在事件生命周期上的可插拔动作（推进 / 输出 / 发现 / 校正）。

负责：算子接口与注册；挂载校验（层级、挂载点、参数）；按类别给最小权限的上下文。
      算子何时被调用由 event 决定，这里不调度。
对外：Operator、OperatorRegistry、Trigger（触发信息）、BaseContext / ProgressContext / SuggestContext、
      build_context、SuggestionSink（建议的去处，由 hil 实现）。
依赖：target（ObservationEnvelope）、condition_engine（EvalResult）、hil（Suggestion）。
扩展点：plugins/operators/ 下继承 Operator。
"""

from core.operators.context import BaseContext, ProgressContext, SuggestContext, build_context
from core.operators.errors import (
    DuplicateOperatorError,
    InvalidMountError,
    OperatorError,
    UnknownOperatorError,
)
from core.operators.operator import Operator
from core.operators.registry import OperatorRegistry
from core.operators.sink import SuggestionSink
from core.operators.trigger import Category, Level, MountPoint, Trigger

__all__ = [
    "BaseContext",
    "Category",
    "DuplicateOperatorError",
    "InvalidMountError",
    "Level",
    "MountPoint",
    "Operator",
    "OperatorError",
    "OperatorRegistry",
    "ProgressContext",
    "SuggestContext",
    "SuggestionSink",
    "Trigger",
    "UnknownOperatorError",
    "build_context",
]
