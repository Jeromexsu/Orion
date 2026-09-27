"""条件引擎：ConditionDef → ConditionCompiler → ConditionTree；扩展点 Evaluator（EvaluatorRegistry 管理）。"""

from core.condition_engine.compiler import ConditionCompiler, FieldsByObservable
from core.condition_engine.definitions import ConditionDef, LeafDef, OpDef
from core.condition_engine.errors import (
    ConditionCompileError,
    ConditionEngineError,
    DuplicateEvaluatorError,
    UnknownEvaluatorError,
)
from core.condition_engine.evaluator import Evaluator
from core.condition_engine.registry import EvaluatorRegistry
from core.condition_engine.result import HIT, MISS, NOT_APPLICABLE, EvalResult, Outcome
from core.condition_engine.tree import ConditionTree, TreeState, apply_state_patch

__all__ = [
    "ConditionCompileError",
    "ConditionDef",
    "ConditionCompiler",
    "ConditionEngineError",
    "ConditionTree",
    "DuplicateEvaluatorError",
    "EvalResult",
    "Evaluator",
    "EvaluatorRegistry",
    "FieldsByObservable",
    "HIT",
    "LeafDef",
    "MISS",
    "NOT_APPLICABLE",
    "OpDef",
    "Outcome",
    "TreeState",
    "UnknownEvaluatorError",
    "apply_state_patch",
]
