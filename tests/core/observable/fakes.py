"""observable 仓库接口、上游目录的内存替身，以及记录收到什么的订阅者。"""

from collections.abc import Sequence

from core.observable import ObservableTarget
from core.observation import ObservationEnvelope, ObservedPoint
from core.target import Target


class InMemoryObservableTargetRepository:
    def __init__(self) -> None:
        self.items: dict[str, ObservableTarget] = {}

    def get(self, key: str) -> ObservableTarget | None:
        return self.items.get(key)

    def upsert(self, observable: ObservableTarget) -> None:
        self.items[observable.id] = observable

    def remove(self, key: str) -> None:
        self.items.pop(key, None)

    def list_active(self) -> list[ObservableTarget]:
        return [o for o in self.items.values() if o.is_active]


class StaticUpstreamCatalog:
    def __init__(self, table: dict[tuple[str, str], list[str]]) -> None:
        self.table = table

    def upstreams_for(
        self, target: Target, observed_point: type[ObservedPoint]
    ) -> Sequence[str]:
        """table 按 (目标类型名, 观察点名) 配置。"""
        return self.table.get((target.type, observed_point.name), [])


class Subscriber:
    def __init__(self) -> None:
        self.received: list[ObservationEnvelope] = []

    def on_observation(self, envelope: ObservationEnvelope) -> None:
        self.received.append(envelope)
