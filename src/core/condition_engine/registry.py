from typing import Any

from core.condition_engine.errors import DuplicateEvaluatorError, UnknownEvaluatorError
from core.condition_engine.evaluator import Evaluator


class EvaluatorRegistry:
    """判断方式注册表，按 Evaluator.type 索引。bootstrap 时注册插件。"""

    def __init__(self) -> None:
        self._evaluators: dict[str, Evaluator[Any]] = {}

    def register(self, evaluator: Evaluator[Any]) -> None:
        """type 重复抛 DuplicateEvaluatorError。"""
        if evaluator.type in self._evaluators:
            raise DuplicateEvaluatorError(evaluator.type)
        self._evaluators[evaluator.type] = evaluator

    def get(self, type_: str) -> Evaluator[Any]:
        """未注册抛 UnknownEvaluatorError。"""
        try:
            return self._evaluators[type_]
        except KeyError:
            raise UnknownEvaluatorError(type_) from None

    def has(self, type_: str) -> bool:
        return type_ in self._evaluators

    def evaluators(self) -> list[Evaluator[Any]]:
        """已注册的全部判断方式。"""
        return list(self._evaluators.values())
