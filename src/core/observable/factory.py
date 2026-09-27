from core.observable.errors import NoUpstreamError, UnsupportedObservedPointError
from core.observable.observable import ObservableTarget
from core.observable.upstream import UpstreamCatalog
from core.observation import ObservedPoint
from core.target import TargetManager


class ObservableTargetFactory:
    """observable 模块的入口：可观测目标的单例工厂，每个 (目标, 观察点) 只有一个 ObservableTarget。

    纯运行时，不存库：可观测目标只存目标 ID 和观察点，能从模板推出来；重启后由 event 重新编译模板、
    重新订阅时再建。目标从 TargetManager 现读，可用上游按当前的目标问 UpstreamCatalog 现算。
    （享元模式里的 FlyweightFactory：按键取共享实例，没有就创建。）
    """

    def __init__(
        self,
        target_manager: TargetManager,
        upstream_catalog: UpstreamCatalog,
    ) -> None:
        self._target_manager = target_manager
        self._upstream_catalog = upstream_catalog
        # 可观测目标 ID → 唯一实例；订阅关系只存在这些对象上
        self._observables: dict[str, ObservableTarget] = {}

    def inspect_observable(
        self, target_id: str, observed_point: str
    ) -> tuple[type[ObservedPoint], tuple[str, ...]]:
        """只查询、不创建：返回 (观察点, 可用上游)。检查与 get_observable 相同，不通过时抛同样的异常。

        可用上游按目标当前的查询键现算（问 UpstreamCatalog），不缓存。
        给只需要校验的调用方（如模板编译）用，避免为最终被拒绝的模板创建可观测目标。

        Raises:
            TargetNotFoundError: 目标不存在（来自 target）。
            UnsupportedObservedPointError: 目标类型没有叫这个名字的观察点（只在本类型的声明里找）。
            NoUpstreamError: 没有上游能在这里观测这个目标。
        """
        target = self._target_manager.get_target(target_id)
        point = next((p for p in type(target).observed_points if p.name == observed_point), None)
        if point is None:
            raise UnsupportedObservedPointError(
                f"{target.type} has no observed point {observed_point!r}"
            )
        upstreams = self._upstream_catalog.upstreams_for(target, point)
        if not upstreams:
            raise NoUpstreamError(f"no upstream can observe {target_id} at {observed_point!r}")
        return point, tuple(upstreams)

    def get_observable(self, target_id: str, observed_point: str) -> ObservableTarget:
        """取（必要时创建）唯一的 ObservableTarget。observed_point 是观察点名。

        首次创建时放进单例表（不写库）；检查与 inspect_observable 相同，不通过时抛同样的异常。
        可观测目标不带可用上游；调用方先用 inspect_observable 查，再自行 subscribe(subscriber, upstreams)。
        """
        key = ObservableTarget.make_id(target_id, observed_point)
        existing = self._observables.get(key)
        if existing is not None:
            return existing

        # 检查：目标存在、支持该观察点、有可用上游
        point, _ = self.inspect_observable(target_id, observed_point)
        observable = ObservableTarget(target_id, point)
        self._observables[key] = observable
        return observable

    def active_observables(self) -> list[ObservableTarget]:
        """subscribers() 非空的 ObservableTarget，collector 只采集这些。"""
        return [o for o in self._observables.values() if o.is_active]

    def observables(self) -> list[ObservableTarget]:
        """已创建的全部 ObservableTarget（有没有订阅者都算）。"""
        return list(self._observables.values())
