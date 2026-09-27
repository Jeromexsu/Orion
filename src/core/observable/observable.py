import logging
from collections.abc import Iterable
from typing import Protocol

from core.observable.errors import UnsupportedUpstreamError
from core.observation import Observation, ObservationEnvelope, ObservedPoint

logger = logging.getLogger(__name__)


class Subscriber(Protocol):
    """订阅 ObservableTarget 的对象（即运行中的子事件模板 EventRunner），由 ObservableTarget.publish 回调。

    实现类必须按身份哈希（普通类默认如此）。
    """

    def on_observation(self, envelope: ObservationEnvelope) -> None:
        """收到一条订阅的观测。只会收到自己订阅过的上游的数据。"""
        ...


class ObservableTarget:
    """A reference to a target at one observed point, plus who subscribes to which
    upstreams. Globally unique; created only by ObservableTargetManager.

    Holds only the target ID, never the target itself: whoever needs the target (its
    query values, its name) reads the current one from TargetManager, so a target
    update needs no notification here. Which upstreams are available is not kept
    either; it is worked out from the current target when needed.

    Subscriptions live in memory only, not persisted: after a restart the event module
    subscribes again.
    """

    def __init__(self, target_id: str, observed_point: type[ObservedPoint]) -> None:
        self._target_id = target_id
        self._observed_point = observed_point
        self._subscriptions: dict[Subscriber, frozenset[str]] = {}

    @staticmethod
    def make_id(target_id: str, observed_point_name: str) -> str:
        """Build the ID of the observable target for a target at an observed point.

        Static because callers often need the ID before the observable target
        exists, e.g. to look it up in ObservableTargetManager's singleton table.

        Returns:
            `<target_id>:<observed_point_name>`, e.g. `t1:position`.
        """
        return f"{target_id}:{observed_point_name}"

    # ------------------------------------------------------------ 只读

    @property
    def id(self) -> str:
        return ObservableTarget.make_id(self._target_id, self._observed_point.name)

    @property
    def target_id(self) -> str:
        return self._target_id

    @property
    def observed_point(self) -> type[ObservedPoint]:
        """观察点：决定这个可观测目标的观测形状。"""
        return self._observed_point

    @property
    def is_active(self) -> bool:
        return bool(self._subscriptions)

    # ------------------------------------------------------------ 订阅

    def subscribe(self, subscriber: Subscriber, upstreams: Iterable[str]) -> None:
        """订阅指定上游。同一订阅者再次 subscribe 会用新的上游集合替换旧的。只改内存，不写库。

        不检查上游是否可用：那取决于当时的目标，由调用方事先查（模板编译时经
        ObservableTargetManager.inspect_observable）；采集时目标已不满足的上游由 collector 跳过。
        上游为空抛 UnsupportedUpstreamError。
        """
        wanted = frozenset(upstreams)
        if not wanted:
            raise UnsupportedUpstreamError(f"{self.id}: subscribe to at least one upstream")
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

    def publish(self, envelope: ObservationEnvelope) -> int:
        """Publish an observation to the subscribers of its upstream.

        Only subscribers that subscribed to envelope.upstream receive it. Each
        subscriber is called in turn and isolated: one that raises is logged and
        does not stop the others. Iterates over a snapshot, so a subscriber may
        unsubscribe during the callback.

        Args:
            envelope: An observation of this observable target.

        Returns:
            Number of subscribers that raised.

        Raises:
            ValueError: If the envelope belongs to another observable target.
        """
        if envelope.observable_id != self.id:
            raise ValueError(f"{self.id} cannot publish an envelope of {envelope.observable_id}")
        failures = 0
        for subscriber in self.subscribers_for(envelope.upstream):
            try:
                subscriber.on_observation(envelope)
            except Exception:
                failures += 1
                logger.exception("subscriber %r failed on %s", subscriber, envelope.source_id)
        return failures

    def active_upstreams(self) -> tuple[str, ...]:
        """至少有一个订阅者的上游，按名字排序。collector 只采集这些。"""
        return tuple(sorted(frozenset[str]().union(*self._subscriptions.values())))

    # ------------------------------------------------------------ 采集辅助

    def accepts(self, observation: Observation) -> bool:
        """这个观测是不是本观察点的观测类（或其子类）的实例。"""
        return isinstance(observation, self._observed_point.observation)
