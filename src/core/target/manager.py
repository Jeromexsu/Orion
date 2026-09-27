from collections.abc import Mapping
from typing import Any

from core.target.errors import (
    NoUpstreamError,
    TargetInUseError,
    TargetNotFoundError,
    TargetTypeChangeError,
    UnknownTargetTypeError,
    UnsupportedObservedPointError,
)
from core.target.observable import ObservableTarget
from core.target.observed_point import ObservedPoint
from core.target.registry import TargetTypeRegistry
from core.target.repository import ObservableTargetRepository, TargetRepository
from core.target.target import Target, TargetRecord
from core.target.upstream import UpstreamCatalog


class TargetManager:
    """target 模块的入口：管目标记录和可观测目标。保证每个 (目标, 观察点) 只有一个 ObservableTarget 实例。

    目标类型和观察点由 TargetTypeRegistry 管（构造时注入），这里只查。
    """

    def __init__(
        self,
        target_type_registry: TargetTypeRegistry,
        target_repository: TargetRepository,
        observable_target_repository: ObservableTargetRepository,
        upstream_catalog: UpstreamCatalog,
    ) -> None:
        self._target_type_registry = target_type_registry
        self._target_repository = target_repository
        self._observable_target_repository = observable_target_repository
        self._upstream_catalog = upstream_catalog
        # 内存里的单例表：订阅者集合只存在这些对象上
        self._live: dict[str, ObservableTarget] = {}

    # ------------------------------------------------------------ 目标

    def parse(self, raw: Mapping[str, Any]) -> Target:
        """JSON → 对应的 Target 子类（按 type 分派）。给 API 层用。属性不合法抛 pydantic.ValidationError。"""
        return self._target_type_registry.get(str(raw.get("type"))).model_validate(raw)

    def upsert_target(self, target: Target) -> Target:
        """新建或更新目标，返回传入的目标。属性校验在构造 Target 子类时已完成。

        写库；已存在的可观测目标换上新记录（rebind_target）。
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
        for point in type(target).observed_points:
            live = self._live.get(ObservableTarget.make_id(target.id, point.name))
            if live is not None:
                live.rebind_target(target)
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
        """删除目标及其所有可观测目标（内存与仓库）。

        不存在抛 TargetNotFoundError；任一可观测目标仍有订阅者抛 TargetInUseError，此时什么都不删。
        """
        target = self.get_target(target_id)
        keys = [ObservableTarget.make_id(target_id, p.name) for p in type(target).observed_points]
        in_use = [k for k in keys if (live := self._live.get(k)) is not None and live.is_active]
        if in_use:
            raise TargetInUseError(f"{target_id} still subscribed via {in_use}")
        for key in keys:
            self._live.pop(key, None)
            self._observable_target_repository.remove(key)
        self._target_repository.remove(target_id)

    # ------------------------------------------------------------ 可观测目标

    def inspect_observable(
        self, target_id: str, observed_point: str
    ) -> tuple[type[ObservedPoint], tuple[str, ...]]:
        """只查询、不创建：返回 (观察点, 可用上游)。检查与 get_observable 相同，不通过时抛同样的异常。

        给只需要校验的调用方（如模板编译）用，避免为最终被拒绝的模板创建可观测目标。
        """
        live = self._live.get(ObservableTarget.make_id(target_id, observed_point))
        if live is not None:
            return live.observed_point, live.upstreams

        point = self._target_type_registry.get_observed_point(observed_point)
        target = self.get_target(target_id)
        if point not in type(target).observed_points:
            raise UnsupportedObservedPointError(
                f"{target.type} cannot be observed at {observed_point!r}"
            )
        upstreams = self._upstream_catalog.upstreams_for(target, point)
        if not upstreams:
            raise NoUpstreamError(f"no upstream can observe {target_id} at {observed_point!r}")
        return point, tuple(upstreams)

    def get_observable(self, target_id: str, observed_point: str) -> ObservableTarget:
        """取（必要时创建）唯一的 ObservableTarget。observed_point 是观察点名。

        首次创建时放进内存单例表并写库；检查与 inspect_observable 相同，不通过时抛同样的异常。
        上游列表由这里问 UpstreamCatalog 得到；调用方随后自行 subscribe(subscriber, upstreams)。
        """
        key = ObservableTarget.make_id(target_id, observed_point)
        live = self._live.get(key)
        if live is not None:
            return live

        point, upstreams = self.inspect_observable(target_id, observed_point)
        observable = ObservableTarget(self.get_target(target_id), point, upstreams)
        self._live[key] = observable
        self._observable_target_repository.upsert(observable)
        return observable

    def active_observables(self) -> list[ObservableTarget]:
        """subscribers() 非空的 ObservableTarget，collector 只采集这些。"""
        return [o for o in self._live.values() if o.is_active]

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
