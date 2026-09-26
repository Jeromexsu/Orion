from pydantic import BaseModel

from core.target.contracts import Target
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
from core.target.target_type import TargetType
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
        self._types: dict[str, TargetType] = {}
        # 内存里的单例表：订阅者集合只存在这些对象上
        self._live: dict[str, ObservableTarget] = {}

    # ------------------------------------------------------------ 类型

    def register_type(self, target_type: TargetType) -> None:
        if target_type.name in self._types:
            raise DuplicateTargetTypeError(target_type.name)
        self._types[target_type.name] = target_type

    def get_type(self, name: str) -> TargetType:
        try:
            return self._types[name]
        except KeyError:
            raise UnknownTargetTypeError(name) from None

    def types(self) -> list[TargetType]:
        return list(self._types.values())

    # ------------------------------------------------------------ 目标

    def upsert_target(self, target: Target) -> Target:
        """校验属性后保存；返回规范化后的记录。属性不合法抛 pydantic.ValidationError。"""
        target_type = self.get_type(target.type)
        existing = self._targets.get(target.id)
        if existing is not None and existing.type != target.type:
            raise TargetTypeChangeError(
                f"target {target.id} is {existing.type}, cannot change to {target.type}"
            )

        attributes = target_type.attributes_model.model_validate(target.attributes).model_dump()
        normalized = target.model_copy(update={"attributes": attributes})

        self._targets.upsert(normalized)
        for focus in target_type.focuses:
            live = self._live.get(observable_key(normalized.id, focus))
            if live is not None:
                live.rebind_target(normalized)
        return normalized

    def get_target(self, target_id: str) -> Target:
        target = self._targets.get(target_id)
        if target is None:
            raise TargetNotFoundError(target_id)
        return target

    def find_by_alias(self, alias: str) -> Target | None:
        return self._targets.find_by_alias(alias)

    def remove_target(self, target_id: str) -> None:
        """删除目标及其所有 ObservableTarget。仍有引用者时拒绝。"""
        target = self.get_target(target_id)
        keys = [observable_key(target_id, focus) for focus in self.get_type(target.type).focuses]
        in_use = [k for k in keys if (live := self._live.get(k)) is not None and live.is_active]
        if in_use:
            raise TargetInUseError(f"{target_id} still referenced via {in_use}")
        for key in keys:
            self._live.pop(key, None)
            self._observables.remove(key)
        self._targets.remove(target_id)

    # ------------------------------------------------------------ 可观测目标

    def get_observable(self, target_id: str, focus: str) -> ObservableTarget:
        """取（必要时创建）唯一的 ObservableTarget。调用方随后自行 acquire()。"""
        key = observable_key(target_id, focus)
        live = self._live.get(key)
        if live is not None:
            return live

        target = self.get_target(target_id)
        schema = self._focus_schema(target, focus)
        upstreams = self._upstreams.upstreams_for(target.type, focus)
        if not upstreams:
            raise NoUpstreamError(f"no upstream serves ({target.type}, {focus})")

        observable = ObservableTarget(target, focus, upstreams, schema)
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
        target = self._targets.get(target_id)
        if target is None or target.type not in self._types:
            return None
        return self._types[target.type].focuses.get(focus)

    # ------------------------------------------------------------ 内部

    def _focus_schema(self, target: Target, focus: str) -> type[BaseModel]:
        schema = self.get_type(target.type).focuses.get(focus)
        if schema is None:
            raise UnsupportedFocusError(f"{target.type} has no focus {focus!r}")
        return schema
