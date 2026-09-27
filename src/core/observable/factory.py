from core.observable.errors import UnsupportedObservedPointError
from core.observable.observable import ObservableTarget
from core.target import TargetManager


class ObservableTargetFactory:
    """observable 模块的入口：可观测目标的单例工厂，每个 (目标, 观察点) 只有一个 ObservableTarget。

    纯运行时，不存库：可观测目标只存目标 ID 和观察点，能从模板推出来；重启后由 event 重新编译模板、
    重新订阅时再建。不管上游能不能用——那是模板编译的校验（event 的 UpstreamCatalog）。
    （享元模式里的 FlyweightFactory：按键取共享实例，没有就创建。）
    """

    def __init__(self, target_manager: TargetManager) -> None:
        self._target_manager = target_manager
        # 可观测目标 ID → 唯一实例；订阅关系只存在这些对象上
        self._observables: dict[str, ObservableTarget] = {}

    def get_observable(self, target_id: str, observed_point: str) -> ObservableTarget:
        """Get the only ObservableTarget of a target at an observed point, creating it once.

        Not stored. Callers normally check a template first (event's TemplateCompiler),
        so a rejected template leaves nothing behind; the checks here guard direct calls.

        Raises:
            TargetNotFoundError: If the target does not exist (from target).
            UnsupportedObservedPointError: If the target's type has no observed point
                with this name.
        """
        key = ObservableTarget.make_id(target_id, observed_point)
        existing = self._observables.get(key)
        if existing is not None:
            return existing

        target = self._target_manager.get_target(target_id)
        point = type(target).find_observed_point(observed_point)
        if point is None:
            raise UnsupportedObservedPointError(
                f"{target.type} has no observed point {observed_point!r}"
            )
        observable = ObservableTarget(target_id, point)
        self._observables[key] = observable
        return observable

    def active_observables(self) -> list[ObservableTarget]:
        """subscribers() 非空的 ObservableTarget，collector 只采集这些。"""
        return [o for o in self._observables.values() if o.is_active]

    def observables(self) -> list[ObservableTarget]:
        """已创建的全部 ObservableTarget（有没有订阅者都算）。"""
        return list(self._observables.values())
