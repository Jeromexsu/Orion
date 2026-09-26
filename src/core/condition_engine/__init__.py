"""条件引擎：EvaluatorRegistry / ConditionEngine / ConditionTree。零依赖。"""

from core.condition_engine.definitions import ConditionDef, LeafDef, OpDef
from core.condition_engine.engine import ConditionEngine
from core.condition_engine.errors import (
    ConditionCompileError,
    ConditionEngineError,
    DuplicateEvaluatorError,
    UnknownEvaluatorError,
)
from core.condition_engine.evaluator import Evaluator
from core.condition_engine.registry import EvaluatorRegistry
from core.condition_engine.resolver import Observation, TargetResolver
from core.condition_engine.result import HIT, MISS, NOT_APPLICABLE, EvalResult, Outcome
from core.condition_engine.tree import ConditionTree, TreeState, apply_state_patch

__all__ = [
    "ConditionCompileError",
    "ConditionDef",
    "ConditionEngine",
    "ConditionEngineError",
    "ConditionTree",
    "DuplicateEvaluatorError",
    "EvalResult",
    "Evaluator",
    "EvaluatorRegistry",
    "HIT",
    "LeafDef",
    "MISS",
    "NOT_APPLICABLE",
    "Observation",
    "OpDef",
    "Outcome",
    "TargetResolver",
    "TreeState",
    "UnknownEvaluatorError",
    "apply_state_patch",
]
