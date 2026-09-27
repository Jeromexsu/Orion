from collections.abc import Mapping
from typing import Any

from core.target.errors import (
    DuplicateObservedPointError,
    DuplicateTargetTypeError,
    NoUpstreamError,
    TargetInUseError,
    TargetNotFoundError,
    TargetTypeChangeError,
    UnknownObservedPointError,
    UnknownTargetTypeError,
    UnsupportedObservedPointError,
)
from core.target.observable import ObservableTarget, observable_key
from core.target.observed_point import ObservedPoint, observed_point_name
from core.target.repository import ObservableTargetRepository, TargetRepository
from core.target.target import Target, TargetRecord, type_name
from core.target.upstream import UpstreamCatalog


class TargetManager:
    """target 模块唯一入口。保证每个 (目标, 观察点) 只有一个 ObservableTarget 实例。

    观察点不单独注册：从已注册目标类型的 observed_points 里收集，按名字建立对照表。
    """

    def __init__(
        self,
        target_repository: TargetRepository,
        observable_target_repository: ObservableTargetRepository,
        upstream_catalog: UpstreamCatalog,
    ) -> None:
        self._target_repository = target_repository
        self._observable_target_repository = observable_target_repository
        self._upstream_catalog = upstream_catalog
        self._types: dict[str, type[Target]] = {}
        self._observed_points: dict[str, type[ObservedPoint]] = {}
        # 内存里的单例表：订阅者集合只存在这些对象上
        self._live: dict[str, ObservableTarget] = {}

    # ------------------------------------------------------------ 类型

    def register_type(self, target_class: type[Target]) -> None:
        """注册一种目标类型，并收集它声明的观察点。

        类型名重复抛 DuplicateTargetTypeError；同名观察点对应不同类抛 DuplicateObservedPointError。
        """
        name = type_name(target_class)
        if name in self._types:
            raise DuplicateTargetTypeError(name)
        points: dict[str, type[ObservedPoint]] = {}
        for point in target_class.observed_points:
            point_name = observed_point_name(point)
            known = self._observed_points.get(point_name) or points.get(point_name)
            if known is not None and known is not point:
                raise DuplicateObservedPointError(
                    f"{point_name!r} is both {known.__name__} and {point.__name__}"
                )
            points[point_name] = point
        self._types[name] = target_class
        self._observed_points.update(points)

    def get_type(self, name: str) -> type[Target]:
        """类型名 → 目标类型。未注册抛 UnknownTargetTypeError。"""
        try:
            return self._types[name]
        except KeyError:
            raise UnknownTargetTypeError(name) from None

    def types(self) -> list[type[Target]]:
        """已注册的全部目标类型。"""
        return list(self._types.values())

    def get_observed_point(self, name: str) -> type[ObservedPoint]:
        """观察点名 → 观察点。没有任何已注册类型声明过抛 UnknownObservedPointError。"""
        try:
            return self._observed_points[name]
        except KeyError:
            raise UnknownObservedPointError(name) from None

    def observed_points(self) -> list[type[ObservedPoint]]:
        """已注册类型声明过的全部观察点。"""
        return list(self._observed_points.values())

    def parse(self, raw: Mapping[str, Any]) -> Target:
        """JSON → 对应的 Target 子类（按 type 分派）。给 API 层用。属性不合法抛 pydantic.ValidationError。"""
        return self.get_type(str(raw.get("type"))).model_validate(raw)

    # ------------------------------------------------------------ 目标

    def upsert_target(self, target: Target) -> Target:
        """新建或更新目标，返回传入的目标。属性校验在构造 Target 子类时已完成。

        写库；已存在的可观测目标换上新记录（rebind_target）。
        类不是该类型名注册的类抛 UnknownTargetTypeError；改变已有目标的类型抛 TargetTypeChangeError。
        """
        if type(target) is not self.get_type(target.type):
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
            live = self._live.get(observable_key(target.id, point.name))
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
        keys = [observable_key(target_id, p.name) for p in type(target).observed_points]
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
        live = self._live.get(observable_key(target_id, observed_point))
        if live is not None:
            return live.observed_point, live.upstreams

        point = self.get_observed_point(observed_point)
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
        key = observable_key(target_id, observed_point)
        live = self._live.get(key)
        if live is not None:
            return live

        point, upstreams = self.inspect_observable(target_id, observed_point)
        observable = ObservableTarget(self.get_target(target_id), point, upstreams)
        self._live[key] = observable
        self._observable_target_repository.upsert(observable)
        return observable

    def find_observable(self, observable_id: str) -> ObservableTarget | None:
        """按 ID 查内存里已存在的 ObservableTarget；不存在返回 None，不创建。"""
        return self._live.get(observable_id)

    def active_observables(self) -> list[ObservableTarget]:
        """subscribers() 非空的 ObservableTarget，collector 只采集这些。"""
        return [o for o in self._live.values() if o.is_active]

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
