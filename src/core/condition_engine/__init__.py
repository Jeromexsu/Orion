"""条件引擎：EvaluatorRegistry / ConditionEngine / ConditionTree。零依赖。"""

from core.condition_engine.contracts import (
    HIT,
    MISS,
    NOT_APPLICABLE,
    ConditionDef,
    EvalResult,
    LeafDef,
    OpDef,
    Outcome,
)
from core.condition_engine.engine import ConditionEngine
from core.condition_engine.errors import (
    ConditionCompileError,
    ConditionEngineError,
    DuplicateEvaluatorError,
    UnknownEvaluatorError,
)
from core.condition_engine.evaluator import LeafEvaluator
from core.condition_engine.registry import EvaluatorRegistry
from core.condition_engine.resolver import Observation, TargetResolver
from core.condition_engine.tree import ConditionTree, TreeState, apply_state_patch

__all__ = [
    "HIT",
    "MISS",
    "NOT_APPLICABLE",
    "ConditionCompileError",
    "ConditionDef",
    "ConditionEngine",
    "ConditionEngineError",
    "ConditionTree",
    "DuplicateEvaluatorError",
    "EvalResult",
    "EvaluatorRegistry",
    "LeafDef",
    "LeafEvaluator",
    "Observation",
    "OpDef",
    "Outcome",
    "TargetResolver",
    "TreeState",
    "UnknownEvaluatorError",
    "apply_state_patch",
]
