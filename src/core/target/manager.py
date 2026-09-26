from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from core.target.errors import (
    DuplicateTargetTypeError,
    NoUpstreamError,
    TargetInUseError,
    TargetNotFoundError,
    TargetTypeChangeError,
    UnknownTargetTypeError,
    UnsupportedFocusError,
)
from core.target.observable import ObservableTarget, observable_key
from core.target.repository import ObservableTargetRepository, TargetRepository
from core.target.target import Target, TargetRecord, type_name
from core.target.upstream import UpstreamCatalog


class TargetManager:
    """target 模块唯一入口。保证每个 (target, focus) 只有一个 ObservableTarget 实例。

    同时结构化地实现 condition engine 的 TargetResolver（见 dynamic_schema）。
    """

    def __init__(
        self,
        targets: TargetRepository,
        observables: ObservableTargetRepository,
        upstreams: UpstreamCatalog,
    ) -> None:
        self._targets = targets
        self._observables = observables
        self._upstreams = upstreams
        self._types: dict[str, type[Target]] = {}
        # 内存里的单例表：订阅者集合只存在这些对象上
        self._live: dict[str, ObservableTarget] = {}

    # ------------------------------------------------------------ 类型

    def register_type(self, target_class: type[Target]) -> None:
        name = type_name(target_class)
        if name in self._types:
            raise DuplicateTargetTypeError(name)
        self._types[name] = target_class

    def get_type(self, name: str) -> type[Target]:
        try:
            return self._types[name]
        except KeyError:
            raise UnknownTargetTypeError(name) from None

    def types(self) -> list[type[Target]]:
        return list(self._types.values())

    def parse(self, raw: Mapping[str, Any]) -> Target:
        """JSON → 对应的 Target 子类（按 type 分派）。给 API 层用。属性不合法抛 pydantic.ValidationError。"""
        return self.get_type(str(raw.get("type"))).model_validate(raw)

    # ------------------------------------------------------------ 目标

    def upsert_target(self, target: Target) -> Target:
        """保存目标。属性校验在构造 Target 子类时已完成。"""
        if type(target) is not self.get_type(target.type):
            raise UnknownTargetTypeError(
                f"{type(target).__name__} is not the registered class for {target.type!r}"
            )
        existing = self._targets.get(target.id)
        if existing is not None and existing.type != target.type:
            raise TargetTypeChangeError(
                f"target {target.id} is {existing.type}, cannot change to {target.type}"
            )

        self._targets.upsert(target.to_record())
        for focus in type(target).focuses:
            live = self._live.get(observable_key(target.id, focus))
            if live is not None:
                live.rebind_target(target)
        return target

    def get_target(self, target_id: str) -> Target:
        record = self._targets.get(target_id)
        if record is None:
            raise TargetNotFoundError(target_id)
        return self._restore(record)

    def find_by_alias(self, alias: str) -> Target | None:
        record = self._targets.find_by_alias(alias)
        return self._restore(record) if record is not None else None

    def remove_target(self, target_id: str) -> None:
        """删除目标及其所有 ObservableTarget。仍有引用者时拒绝。"""
        target = self.get_target(target_id)
        keys = [observable_key(target_id, focus) for focus in type(target).focuses]
        in_use = [k for k in keys if (live := self._live.get(k)) is not None and live.is_active]
        if in_use:
            raise TargetInUseError(f"{target_id} still referenced via {in_use}")
        for key in keys:
            self._live.pop(key, None)
            self._observables.remove(key)
        self._targets.remove(target_id)

    # ------------------------------------------------------------ 可观测目标

    def get_observable(self, target_id: str, focus: str) -> ObservableTarget:
        """取（必要时创建）唯一的 ObservableTarget。上游列表由这里问 UpstreamCatalog 得到。

        调用方随后自行 acquire(referencer, upstreams) 订阅需要的上游。
        """
        key = observable_key(target_id, focus)
        live = self._live.get(key)
        if live is not None:
            return live

        target = self.get_target(target_id)
        if focus not in type(target).focuses:
            raise UnsupportedFocusError(f"{target.type} has no focus {focus!r}")
        upstreams = self._upstreams.upstreams_for(target.type, focus)
        if not upstreams:
            raise NoUpstreamError(f"no upstream serves ({target.type}, {focus})")

        observable = ObservableTarget(target, focus, upstreams)
        self._live[key] = observable
        self._observables.upsert(observable)
        return observable

    def find_observable(self, observable_id: str) -> ObservableTarget | None:
        """按 ID 查内存里已存在的 ObservableTarget。"""
        return self._live.get(observable_id)

    def active_observables(self) -> list[ObservableTarget]:
        """referencers() 非空的 ObservableTarget，collector 只采集这些。"""
        return [o for o in self._live.values() if o.is_active]

    # ------------------------------------------------------------ TargetResolver

    def dynamic_schema(self, observable_id: str) -> type[BaseModel] | None:
        """供 condition engine 查字段 schema；ObservableTarget 尚未创建也能解析。"""
        live = self._live.get(observable_id)
        if live is not None:
            return live.dynamic_schema
        target_id, sep, focus = observable_id.rpartition(":")
        if not sep:
            return None
        record = self._targets.get(target_id)
        if record is None or record.type not in self._types:
            return None
        return self._types[record.type].focuses.get(focus)

    # ------------------------------------------------------------ 内部

    def _restore(self, record: TargetRecord) -> Target:
        """持久化记录 → 对应的 Target 子类。"""
        return self.get_type(record.type).model_validate(
            {
                "type": record.type,
                "id": record.id,
                "name": record.name,
                "aliases": record.aliases,
                **record.attributes,
            }
        )
