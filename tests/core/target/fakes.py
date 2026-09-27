"""target 仓库接口的内存替身，以及测试用的目标类型。"""

from core.observation import Observation, ObservedPoint, observed_point
from core.target import Target, TargetRecord, target_type
from plugins.observed_points.position import Position


class InMemoryTargetRepository:
    def __init__(self) -> None:
        self.items: dict[str, TargetRecord] = {}

    def get(self, target_id: str) -> TargetRecord | None:
        return self.items.get(target_id)

    def upsert(self, target: TargetRecord) -> None:
        self.items[target.id] = target

    def remove(self, target_id: str) -> None:
        self.items.pop(target_id, None)

    def find_by_alias(self, alias: str) -> TargetRecord | None:
        return next((t for t in self.items.values() if alias in t.aliases), None)


class DraughtObservation(Observation):
    metres: float


@observed_point("draught", observation=DraughtObservation)
class Draught(ObservedPoint):
    """船特有的观察点：吃水。"""


@target_type("ship", observed_points=[Position, Draught])
class Ship(Target):
    """船和飞机共用 Position 观察点。"""

    mmsi: str
