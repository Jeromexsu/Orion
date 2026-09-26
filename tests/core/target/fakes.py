"""target 仓库接口的内存替身。"""

from collections.abc import Sequence

from core.target import ObservableTarget, TargetRecord


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

    def upstreams_for(self, target_type: str, focus: str) -> Sequence[str]:
        return self.table.get((target_type, focus), [])
