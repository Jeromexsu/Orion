from core.observable.errors import NoUpstreamError, UnsupportedObservedPointError
from core.observable.observable import ObservableTarget
from core.observable.repository import ObservableTargetRepository
from core.observable.upstream import UpstreamCatalog
from core.observation import ObservedPoint
from core.target import TargetManager, TargetTypeRegistry


class ObservableTargetManager:
    """observable 模块的入口：保证每个 (目标, 观察点) 只有一个 ObservableTarget（单例表）。

    可观测目标只存目标 ID；目标从 TargetManager 现读，可用上游按当前的目标问 UpstreamCatalog 现算。
    """

    def __init__(
        self,
        target_type_registry: TargetTypeRegistry,
        target_manager: TargetManager,
        observable_target_repository: ObservableTargetRepository,
        upstream_catalog: UpstreamCatalog,
    ) -> None:
        self._target_type_registry = target_type_registry
        self._target_manager = target_manager
        self._observable_target_repository = observable_target_repository
        self._upstream_catalog = upstream_catalog
        # 内存里的单例表：订阅者集合只存在这些对象上
        self._live: dict[str, ObservableTarget] = {}

    def inspect_observable(
        self, target_id: str, observed_point: str
    ) -> tuple[type[ObservedPoint], tuple[str, ...]]:
        """只查询、不创建：返回 (观察点, 可用上游)。检查与 get_observable 相同，不通过时抛同样的异常。

        可用上游按目标当前的查询键现算（问 UpstreamCatalog），不缓存。
        给只需要校验的调用方（如模板编译）用，避免为最终被拒绝的模板创建可观测目标。

        Raises:
            UnknownObservedPointError: 没有已注册目标类型声明过这个观察点（来自 target）。
            TargetNotFoundError: 目标不存在（来自 target）。
            UnsupportedObservedPointError: 目标类型没有声明这个观察点。
            NoUpstreamError: 没有上游能在这里观测这个目标。
        """
        point = self._target_type_registry.get_observed_point(observed_point)
        target = self._target_manager.get_target(target_id)
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
        可观测目标不带可用上游；调用方先用 inspect_observable 查，再自行 subscribe(subscriber, upstreams)。
        """
        key = ObservableTarget.make_id(target_id, observed_point)
        live = self._live.get(key)
        if live is not None:
            return live

        # 检查：目标存在、支持该观察点、有可用上游
        point, _ = self.inspect_observable(target_id, observed_point)
        observable = ObservableTarget(target_id, point)
        self._live[key] = observable
        self._observable_target_repository.upsert(observable)
        return observable

    def active_observables(self) -> list[ObservableTarget]:
        """subscribers() 非空的 ObservableTarget，collector 只采集这些。"""
        return [o for o in self._live.values() if o.is_active]
