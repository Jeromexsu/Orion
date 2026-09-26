from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel

from core.contracts import DynamicData, QuerySpec
from core.target.contracts import Target
from core.target.errors import UnsupportedFocusError, UnsupportedUpstreamError


class Referencer(Protocol):
    """订阅 ObservableTarget 的对象（即运行中的子事件模板 SubEventSlot），由 Dispatcher 回调。

    实现类必须按身份哈希（普通类默认如此）。
    """

    def on_data(self, data: DynamicData) -> None: ...


def observable_key(target_id: str, focus: str) -> str:
    return f"{target_id}:{focus}"


class ObservableTarget:
    """具体目标实例 + 一个关注点，全局唯一（只由 TargetManager 创建）。

    upstreams 是 TargetManager 问 UpstreamCatalog 得到的全部可用上游。
    订阅者 acquire 时指定要哪些上游，对象内部维护路由：某个上游的数据
    只推给订阅了该上游的订阅者。某个上游没人订阅就不采集。
    订阅关系只在内存里，不持久化——重启后由 event 模块重新 acquire。
    """

    def __init__(self, target: Target, focus: str, upstreams: Sequence[str]) -> None:
        schema = type(target).focuses.get(focus)
        if schema is None:
            raise UnsupportedFocusError(f"{target.type} has no focus {focus!r}")
        if not upstreams:
            raise UnsupportedUpstreamError(f"no upstream for ({target.type}, {focus})")
        self._target = target
        self._focus = focus
        self._dynamic_schema = schema
        self._upstreams = tuple(upstreams)
        self._subscriptions: dict[Referencer, frozenset[str]] = {}

    # ------------------------------------------------------------ 只读

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
        """全部可用上游。"""
        return self._upstreams

    @property
    def dynamic_schema(self) -> type[BaseModel]:
        return self._dynamic_schema

    @property
    def is_active(self) -> bool:
        return bool(self._subscriptions)

    # ------------------------------------------------------------ 订阅

    def acquire(self, referencer: Referencer, upstreams: Iterable[str]) -> None:
        """订阅指定上游。同一订阅者再次 acquire 会用新的上游集合替换旧的。"""
        wanted = frozenset(upstreams)
        if not wanted:
            raise UnsupportedUpstreamError(f"{self.id}: subscribe to at least one upstream")
        unknown = wanted - set(self._upstreams)
        if unknown:
            raise UnsupportedUpstreamError(
                f"{self.id}: {sorted(unknown)} not in available upstreams {list(self._upstreams)}"
            )
        self._subscriptions[referencer] = wanted

    def release(self, referencer: Referencer) -> None:
        """取消订阅。未订阅过的对象忽略。"""
        self._subscriptions.pop(referencer, None)

    def subscription(self, referencer: Referencer) -> frozenset[str]:
        """某个订阅者订阅的上游；未订阅返回空集。"""
        return self._subscriptions.get(referencer, frozenset())

    def referencers(self) -> frozenset[Referencer]:
        """全部订阅者的快照。"""
        return frozenset(self._subscriptions)

    def referencers_for(self, upstream: str) -> frozenset[Referencer]:
        """订阅了该上游的订阅者快照；回调期间有人 release 也不影响遍历。"""
        return frozenset(r for r, ups in self._subscriptions.items() if upstream in ups)

    def active_upstreams(self) -> tuple[str, ...]:
        """至少有一个订阅者的上游，按可用上游的顺序。collector 只采集这些。"""
        subscribed = frozenset[str]().union(*self._subscriptions.values())
        return tuple(u for u in self._upstreams if u in subscribed)

    # ------------------------------------------------------------ 采集辅助

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
