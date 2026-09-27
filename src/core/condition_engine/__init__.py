"""条件引擎：把条件定义编译成条件树，对一条观测给出三值判断。

负责：ConditionDef --ConditionCompiler.compile--> ConditionTree；ConditionTree.evaluate(观测外壳, 状态) → EvalResult。
      纯计算：不存状态、不订阅；状态由调用方保管，结果的 state 是新状态（None 表示没变）。
对外：ConditionCompiler、ConditionTree、EvalResult（命中 / 未命中 / 不适用）、Evaluator、EvaluatorRegistry。
依赖：target（只用 ObservationEnvelope，见 docs/open-questions.md 第 5 条）。
扩展点：plugins/condition_engine/ 下继承 Evaluator（一种判断方式）。
"""

from core.condition_engine.compiler import ConditionCompiler, DeclaredObservables
from core.condition_engine.definitions import BranchDef, ConditionDef, LeafDef
from core.condition_engine.errors import (
    ConditionCompileError,
    ConditionEngineError,
    DuplicateEvaluatorError,
    UnknownEvaluatorError,
)
from core.condition_engine.evaluator import (
    HIT,
    MISS,
    NOT_APPLICABLE,
    EvalResult,
    Evaluator,
    Outcome,
)
from core.condition_engine.registry import EvaluatorRegistry
from core.condition_engine.tree import ConditionTree, TreeState

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
    "DeclaredObservables",
    "HIT",
    "LeafDef",
    "MISS",
    "NOT_APPLICABLE",
    "BranchDef",
    "Outcome",
    "TreeState",
    "UnknownEvaluatorError",
]
