from typing import Any

from pydantic import BaseModel, ValidationError

from core.contracts import Level, MountPoint
from core.operators.errors import DuplicateOperatorError, InvalidMountError, UnknownOperatorError
from core.operators.operator import Operator


class OperatorRegistry:
    def __init__(self) -> None:
        self._operators: dict[str, Operator[Any]] = {}

    def register(self, operator: Operator[Any]) -> None:
        if operator.name in self._operators:
            raise DuplicateOperatorError(operator.name)
        self._operators[operator.name] = operator

    def get(self, name: str) -> Operator[Any]:
        try:
            return self._operators[name]
        except KeyError:
            raise UnknownOperatorError(name) from None

    def operators(self) -> list[Operator[Any]]:
        return list(self._operators.values())

    def validate_mount(
        self, name: str, level: Level, mount_point: MountPoint, params: dict[str, Any]
    ) -> BaseModel:
        """模板挂载算子时的校验：层级、挂载点、参数。返回解析后的参数。"""
        operator = self.get(name)
        if level not in operator.levels:
            raise InvalidMountError(f"{name} cannot mount at level {level!r}")
        if mount_point not in operator.mount_points:
            raise InvalidMountError(f"{name} cannot mount at {mount_point!r}")
        try:
            return operator.params_model.model_validate(params)
        except ValidationError as e:
            raise InvalidMountError(f"invalid params for {name}: {e}") from e
