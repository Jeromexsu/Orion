from collections.abc import Sequence
from datetime import datetime

from core.collector import FetchedRecord
from core.target import ObservationEnvelope, ObservedPoint, QuerySpec
from plugins.observed_points.position import Position


class FakeAdapter:
    def __init__(
        self,
        name: str,
        observed_point: type[ObservedPoint] = Position,
        query_field_sets: tuple[frozenset[str], ...] = (frozenset({"registration"}),),
        records: list[FetchedRecord] | None = None,
    ) -> None:
        self.name = name
        self.observed_point = observed_point
        self.query_field_sets = query_field_sets
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
        self.items: dict[tuple[str, str], str] = {}

    def get(self, observable_id: str, upstream: str) -> str | None:
        return self.items.get((observable_id, upstream))

    def set(self, observable_id: str, upstream: str, cursor: str) -> None:
        self.items[(observable_id, upstream)] = cursor


class InMemoryObservationRepository:
    def __init__(self) -> None:
        self.items: list[ObservationEnvelope] = []

    def append(self, envelope: ObservationEnvelope) -> None:
        self.items.append(envelope)

    def exists(self, source_id: str) -> bool:
        return any(d.source_id == source_id for d in self.items)

    def history(
        self, observable_id: str, since: datetime | None = None
    ) -> list[ObservationEnvelope]:
        return [
            d
            for d in self.items
            if d.observable_id == observable_id and (since is None or d.occurred_at > since)
        ]
