from collections.abc import Iterable, Sequence
from typing import Protocol

from core.target.data import ObservationEnvelope
from core.target.errors import UnsupportedObservedPointError, UnsupportedUpstreamError
from core.target.observed_point import Observation, ObservedPoint
from core.target.target import Target


class Subscriber(Protocol):
    """订阅 ObservableTarget 的对象（即运行中的子事件模板 EventRunner），由 Dispatcher 回调。

    实现类必须按身份哈希（普通类默认如此）。
    """

    def on_observation(self, envelope: ObservationEnvelope) -> None:
        """收到一条订阅的观测。只会收到自己订阅过的上游的数据。"""
        ...


def observable_key(target_id: str, observed_point_name: str) -> str:
    """可观测目标 ID：`目标ID:观察点名`，如 `t1:position`。"""
    return f"{target_id}:{observed_point_name}"


class ObservableTarget:
    """具体目标实例 + 一个观察点，全局唯一（只由 TargetManager 创建）。

    upstreams 是 TargetManager 问 UpstreamCatalog 得到的全部可用上游。
    订阅者 subscribe 时指定要哪些上游，对象内部维护路由：某个上游的数据
    只推给订阅了该上游的订阅者。某个上游没人订阅就不采集。
    订阅关系只在内存里，不持久化——重启后由 event 模块重新订阅。
    """

    def __init__(
        self, target: Target, observed_point: type[ObservedPoint], upstreams: Sequence[str]
    ) -> None:
        if observed_point not in type(target).observed_points:
            raise UnsupportedObservedPointError(
                f"{target.type} cannot be observed at {observed_point.name!r}"
            )
        if not upstreams:
            raise UnsupportedUpstreamError(
                f"no upstream for {target.id} at {observed_point.name!r}"
            )
        self._target = target
        self._observed_point = observed_point
        self._upstreams = tuple(upstreams)
        self._subscriptions: dict[Subscriber, frozenset[str]] = {}

    # ------------------------------------------------------------ 只读

    @property
    def id(self) -> str:
        return observable_key(self._target.id, self._observed_point.name)

    @property
    def target(self) -> Target:
        return self._target

    @property
    def observed_point(self) -> type[ObservedPoint]:
        """观察点：决定这个可观测目标的观测形状。"""
        return self._observed_point

    @property
    def upstreams(self) -> tuple[str, ...]:
        """全部可用上游。"""
        return self._upstreams

    @property
    def is_active(self) -> bool:
        return bool(self._subscriptions)

    # ------------------------------------------------------------ 订阅

    def subscribe(self, subscriber: Subscriber, upstreams: Iterable[str]) -> None:
        """订阅指定上游。同一订阅者再次 subscribe 会用新的上游集合替换旧的。

        上游为空或不在可用上游里抛 UnsupportedUpstreamError。只改内存，不写库。
        """
        wanted = frozenset(upstreams)
        if not wanted:
            raise UnsupportedUpstreamError(f"{self.id}: subscribe to at least one upstream")
        unknown = wanted - set(self._upstreams)
        if unknown:
            raise UnsupportedUpstreamError(
                f"{self.id}: {sorted(unknown)} not in available upstreams {list(self._upstreams)}"
            )
        self._subscriptions[subscriber] = wanted

    def unsubscribe(self, subscriber: Subscriber) -> None:
        """取消订阅。未订阅过的对象忽略。"""
        self._subscriptions.pop(subscriber, None)

    def subscription(self, subscriber: Subscriber) -> frozenset[str]:
        """某个订阅者订阅的上游；未订阅返回空集。"""
        return self._subscriptions.get(subscriber, frozenset())

    def subscribers(self) -> frozenset[Subscriber]:
        """全部订阅者的快照。"""
        return frozenset(self._subscriptions)

    def subscribers_for(self, upstream: str) -> frozenset[Subscriber]:
        """订阅了该上游的订阅者快照；回调期间有人 unsubscribe 也不影响遍历。"""
        return frozenset(r for r, ups in self._subscriptions.items() if upstream in ups)

    def active_upstreams(self) -> tuple[str, ...]:
        """至少有一个订阅者的上游，按可用上游的顺序。collector 只采集这些。"""
        subscribed = frozenset[str]().union(*self._subscriptions.values())
        return tuple(u for u in self._upstreams if u in subscribed)

    # ------------------------------------------------------------ 采集辅助

    def accepts(self, observation: Observation) -> bool:
        """这个观测是不是本观察点的观测类（或其子类）的实例。"""
        return isinstance(observation, self._observed_point.observation)

    def rebind_target(self, target: Target) -> None:
        """目标记录更新后换上新记录。只应由 TargetManager 调用。"""
        if target.id != self._target.id:
            raise ValueError(f"cannot rebind {self.id} to target {target.id}")
        self._target = target
