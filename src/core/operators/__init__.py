"""算子核心：OperatorRegistry / Operator / 三种 Context / SuggestionSink / Trigger。

依赖 target（ObservationEnvelope）、condition_engine（EvalResult）、hil（Suggestion）。"""

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
