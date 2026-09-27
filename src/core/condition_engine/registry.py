from typing import Any

from core.condition_engine.errors import DuplicateEvaluatorError, UnknownEvaluatorError
from core.condition_engine.evaluator import Evaluator


class EvaluatorRegistry:
    """判断方式注册表，按 Evaluator.op 索引。bootstrap 时注册插件。"""

    def __init__(self) -> None:
        self._evaluators: dict[str, Evaluator[Any, Any]] = {}

    def register(self, evaluator: Evaluator[Any, Any]) -> None:
        """没用 @evaluator 声明抛 TypeError；op 重复抛 DuplicateEvaluatorError。"""
        _check_declared(evaluator)
        if evaluator.op in self._evaluators:
            raise DuplicateEvaluatorError(evaluator.op)
        self._evaluators[evaluator.op] = evaluator

    def get(self, op: str) -> Evaluator[Any, Any]:
        """未注册抛 UnknownEvaluatorError。"""
        try:
            return self._evaluators[op]
        except KeyError:
            raise UnknownEvaluatorError(op) from None


def _check_declared(evaluator: Evaluator[Any, Any]) -> None:
    """Raise TypeError unless the evaluator's class was declared with @evaluator."""
    if not all(hasattr(evaluator, a) for a in ("op", "criteria_model", "observation_model")):
        raise TypeError(f"{type(evaluator).__name__} must be declared with @evaluator(...)")
