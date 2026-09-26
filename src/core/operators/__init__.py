"""算子核心：OperatorRegistry / Operator / 三种 Context / SuggestionSink。只依赖 contracts。"""

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

__all__ = [
    "BaseContext",
    "DuplicateOperatorError",
    "InvalidMountError",
    "Operator",
    "OperatorError",
    "OperatorRegistry",
    "ProgressContext",
    "SuggestContext",
    "SuggestionSink",
    "UnknownOperatorError",
    "build_context",
]
