from collections.abc import Sequence
from datetime import datetime

from core.collector import FetchedRecord
from core.contracts import DynamicData, QuerySpec


class FakeAdapter:
    def __init__(
        self, name: str, serves: set[tuple[str, str]], records: list[FetchedRecord] | None = None
    ) -> None:
        self.name = name
        self.serves = frozenset(serves)
        self.records = records or []
        self.specs: list[QuerySpec] = []
        self.fail = False

    def fetch(self, spec: QuerySpec) -> Sequence[FetchedRecord]:
        self.specs.append(spec)
        if self.fail:
            raise RuntimeError("upstream down")
        return [r for r in self.records if spec.since is None or r.occurred_at > spec.since]


class InMemoryCursorRepository:
    def __init__(self) -> None:
        self.items: dict[str, str] = {}

    def get(self, observable_id: str) -> str | None:
        return self.items.get(observable_id)

    def set(self, observable_id: str, cursor: str) -> None:
        self.items[observable_id] = cursor


class InMemoryDynamicDataRepository:
    def __init__(self) -> None:
        self.items: list[DynamicData] = []

    def append(self, data: DynamicData) -> None:
        self.items.append(data)

    def exists(self, source_id: str) -> bool:
        return any(d.source_id == source_id for d in self.items)

    def history(self, observable_id: str, since: datetime | None = None) -> list[DynamicData]:
        return [
            d
            for d in self.items
            if d.observable_id == observable_id and (since is None or d.occurred_at > since)
        ]
