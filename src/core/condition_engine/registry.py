from typing import Any

from core.condition_engine.errors import DuplicateEvaluatorError, UnknownEvaluatorError
from core.condition_engine.evaluator import Evaluator


class EvaluatorRegistry:
    """判断方式注册表，按 Evaluator.op 索引。bootstrap 时注册插件。"""

    def __init__(self) -> None:
        self._evaluators: dict[str, Evaluator[Any]] = {}

    def register(self, evaluator: Evaluator[Any]) -> None:
        """op 重复抛 DuplicateEvaluatorError。"""
        if evaluator.op in self._evaluators:
            raise DuplicateEvaluatorError(evaluator.op)
        self._evaluators[evaluator.op] = evaluator

    def get(self, op: str) -> Evaluator[Any]:
        """未注册抛 UnknownEvaluatorError。"""
        try:
            return self._evaluators[op]
        except KeyError:
            raise UnknownEvaluatorError(op) from None

    def has(self, op: str) -> bool:
        return op in self._evaluators

    def evaluators(self) -> list[Evaluator[Any]]:
        """已注册的全部判断方式。"""
        return list(self._evaluators.values())
