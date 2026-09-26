from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel

from core.contracts import DynamicData, QuerySpec
from core.target.contracts import Target


class Referencer(Protocol):
    """引用 ObservableTarget 的订阅者（通常是 ParentEvent），由 Dispatcher 回调。

    实现类必须按身份哈希（普通类默认如此）。
    """

    def on_data(self, data: DynamicData) -> None: ...


def observable_key(target_id: str, focus: str) -> str:
    return f"{target_id}:{focus}"


class ObservableTarget:
    """Target + 关注点 + 上游，全局唯一（由 TargetManager 保证）。

    只在 referencers() 非空时被采集；最后一个引用者 release 后自动停止监控。
    订阅者集合只在内存里，不持久化——重启后由 event 模块重新 acquire。
    """

    def __init__(
        self,
        target: Target,
        focus: str,
        upstreams: Sequence[str],
        dynamic_schema: type[BaseModel],
    ) -> None:
        self._target = target
        self._focus = focus
        self._upstreams = tuple(upstreams)
        self._dynamic_schema = dynamic_schema
        self._referencers: set[Referencer] = set()

    @property
    def id(self) -> str:
        return observable_key(self._target.id, self._focus)

    @property
    def target(self) -> Target:
        return self._target

    @property
    def focus(self) -> str:
        return self._focus

    @property
    def upstreams(self) -> tuple[str, ...]:
        return self._upstreams

    @property
    def dynamic_schema(self) -> type[BaseModel]:
        return self._dynamic_schema

    @property
    def is_active(self) -> bool:
        return bool(self._referencers)

    def acquire(self, referencer: Referencer) -> None:
        """登记一个引用者。重复登记同一对象是幂等的。"""
        self._referencers.add(referencer)

    def release(self, referencer: Referencer) -> None:
        """注销一个引用者。未登记过的对象忽略。"""
        self._referencers.discard(referencer)

    def referencers(self) -> frozenset[Referencer]:
        """当前引用者的快照；回调期间有人 release 也不影响遍历。"""
        return frozenset(self._referencers)

    def query_spec(self, since: datetime | None = None) -> QuerySpec:
        return QuerySpec(
            type=self._target.type,
            focus=self._focus,
            attributes=self._target.attributes(),
            aliases=self._target.aliases,
            since=since,
        )

    def validate_fields(self, fields: Mapping[str, Any]) -> dict[str, Any]:
        """按 dynamic_schema 校验上游字段，返回规范化后的 dict。失败抛 pydantic.ValidationError。"""
        return self._dynamic_schema.model_validate(fields).model_dump()

    def rebind_target(self, target: Target) -> None:
        """目标记录更新后换上新记录。只应由 TargetManager 调用。"""
        if target.id != self._target.id:
            raise ValueError(f"cannot rebind {self.id} to target {target.id}")
        self._target = target
