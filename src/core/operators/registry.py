from typing import Any

from core.operators.errors import DuplicateOperatorError, UnknownOperatorError
from core.operators.operator import Operator


class OperatorRegistry:
    """算子注册表，按 Operator.name 索引。bootstrap 时注册插件。

    只注册和查找；模板里的挂载是否合法由模板编译器检查。
    """

    def __init__(self) -> None:
        self._operators: dict[str, Operator[Any]] = {}

    def register(self, operator: Operator[Any]) -> None:
        """没用 @operator 声明抛 TypeError；名字重复抛 DuplicateOperatorError。"""
        _check_declared(operator)
        if operator.name in self._operators:
            raise DuplicateOperatorError(operator.name)
        self._operators[operator.name] = operator

    def get(self, name: str) -> Operator[Any]:
        """未注册抛 UnknownOperatorError。"""
        try:
            return self._operators[name]
        except KeyError:
            raise UnknownOperatorError(name) from None

    def operators(self) -> list[Operator[Any]]:
        """已注册的全部算子。"""
        return list(self._operators.values())


def _check_declared(operator: Operator[Any]) -> None:
    """Raise TypeError unless the operator's class was declared with @operator."""
    attrs = ("name", "mount_points", "scopes", "proposes", "params_model")
    if not all(hasattr(operator, a) for a in attrs):
        raise TypeError(f"{type(operator).__name__} must be declared with @operator(...)")
