from typing import Any

from pydantic import BaseModel, ValidationError

from core.operators.errors import DuplicateOperatorError, InvalidMountError, UnknownOperatorError
from core.operators.operator import Operator
from core.operators.trigger import Level, MountPoint


class OperatorRegistry:
    """算子注册表，按 Operator.name 索引。bootstrap 时注册插件。"""

    def __init__(self) -> None:
        self._operators: dict[str, Operator[Any]] = {}

    def register(self, operator: Operator[Any]) -> None:
        """名字重复抛 DuplicateOperatorError。"""
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

    def validate_mount(
        self, name: str, level: Level, mount_point: MountPoint, params: dict[str, Any]
    ) -> BaseModel:
        """模板挂载算子时的校验：层级、挂载点、参数。返回解析后的参数。

        算子不存在抛 UnknownOperatorError；其余不合法抛 InvalidMountError。无副作用。
        """
        operator = self.get(name)
        if level not in operator.levels:
            raise InvalidMountError(f"{name} cannot mount at level {level!r}")
        if mount_point not in operator.mount_points:
            raise InvalidMountError(f"{name} cannot mount at {mount_point!r}")
        try:
            return operator.params_model.model_validate(params)
        except ValidationError as e:
            raise InvalidMountError(f"invalid params for {name}: {e}") from e
