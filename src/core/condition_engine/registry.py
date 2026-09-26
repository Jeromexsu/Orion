from typing import Any

from core.condition_engine.errors import DuplicateEvaluatorError, UnknownEvaluatorError
from core.condition_engine.evaluator import LeafEvaluator


class EvaluatorRegistry:
    def __init__(self) -> None:
        self._evaluators: dict[str, LeafEvaluator[Any]] = {}

    def register(self, evaluator: LeafEvaluator[Any]) -> None:
        if evaluator.type in self._evaluators:
            raise DuplicateEvaluatorError(evaluator.type)
        self._evaluators[evaluator.type] = evaluator

    def get(self, type_: str) -> LeafEvaluator[Any]:
        try:
            return self._evaluators[type_]
        except KeyError:
            raise UnknownEvaluatorError(type_) from None

    def has(self, type_: str) -> bool:
        return type_ in self._evaluators

    def evaluators(self) -> list[LeafEvaluator[Any]]:
        return list(self._evaluators.values())
