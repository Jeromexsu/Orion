from collections.abc import Mapping
from typing import Any

from core.target.errors import (
    TargetNotFoundError,
    TargetTypeChangeError,
    UnknownTargetTypeError,
)
from core.target.registry import TargetTypeRegistry
from core.target.repository import TargetRepository
from core.target.target import Target, TargetRecord


class TargetManager:
    """target 模块的入口：管目标实例（目标记录）的生命周期。

    目标类型由 TargetTypeRegistry 管（构造时注入），这里只查。别的模块只按 ID 引用目标、用到时现读，
    所以改目标不用通知谁。
    """

    def __init__(
        self, target_type_registry: TargetTypeRegistry, target_repository: TargetRepository
    ) -> None:
        self._target_type_registry = target_type_registry
        self._target_repository = target_repository

    # ------------------------------------------------------------ 目标

    def parse(self, raw: Mapping[str, Any]) -> Target:
        """JSON → 对应的 Target 子类（按 type 分派）。给 API 层用。属性不合法抛 pydantic.ValidationError。"""
        return self._target_type_registry.get(str(raw.get("type"))).model_validate(raw)

    def upsert_target(self, target: Target) -> Target:
        """新建或更新目标，返回传入的目标。属性校验在构造 Target 子类时已完成。

        写库。引用目标的一方只存目标 ID、用到时现读，所以不用通知它们。
        类不是该类型名注册的类抛 UnknownTargetTypeError；改变已有目标的类型抛 TargetTypeChangeError。
        """
        if type(target) is not self._target_type_registry.get(target.type):
            raise UnknownTargetTypeError(
                f"{type(target).__name__} is not the registered class for {target.type!r}"
            )
        existing = self._target_repository.get(target.id)
        if existing is not None and existing.type != target.type:
            raise TargetTypeChangeError(
                f"target {target.id} is {existing.type}, cannot change to {target.type}"
            )

        self._target_repository.upsert(target.to_record())
        return target

    def get_target(self, target_id: str) -> Target:
        """从仓库读出目标并还原成具体子类。不存在抛 TargetNotFoundError。"""
        record = self._target_repository.get(target_id)
        if record is None:
            raise TargetNotFoundError(target_id)
        return self._restore(record)

    def find_by_alias(self, alias: str) -> Target | None:
        """按别名找目标；找不到返回 None。"""
        record = self._target_repository.find_by_alias(alias)
        return self._restore(record) if record is not None else None

    def remove_target(self, target_id: str) -> None:
        """Remove a target (stored).

        Does not check whether anything still refers to it: whoever refers to targets by
        ID tolerates one that is gone (e.g. the collector logs and skips). Archiving
        instead of removing is an open question (docs/open-questions.md).

        Raises:
            TargetNotFoundError: If it does not exist.
        """
        self.get_target(target_id)
        self._target_repository.remove(target_id)

    # ------------------------------------------------------------ 内部

    def _restore(self, record: TargetRecord) -> Target:
        """持久化记录 → 对应的 Target 子类。"""
        return self._target_type_registry.get(record.type).model_validate(
            {
                "type": record.type,
                "id": record.id,
                "name": record.name,
                "aliases": record.aliases,
                **record.attributes,
            }
        )
