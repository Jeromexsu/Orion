from collections.abc import Sequence
from datetime import datetime

from core.collector import Adapter, FetchedRecord, Query
from core.target import ObservationEnvelope, ObservedPoint, QueryKey
from plugins.observed_points.position import Position
from plugins.query_keys.registration import Registration


class FetchCall:
    """记录一次 fetch 收到的参数。"""

    def __init__(
        self, observed_point: type[ObservedPoint], query: Query, since: datetime | None
    ) -> None:
        self.observed_point = observed_point
        self.query = query
        self.since = since


class FakeAdapter(Adapter):
    def __init__(
        self,
        name: str,
        observed_points: frozenset[type[ObservedPoint]] = frozenset({Position}),
        query_key_sets: tuple[frozenset[type[QueryKey]], ...] = (frozenset({Registration}),),
        records: list[FetchedRecord] | None = None,
    ) -> None:
        self.name = name
        self.observed_points = observed_points
        self.query_key_sets = query_key_sets
        self.records = records or []
        self.calls: list[FetchCall] = []
        self.fail = False

    def fetch(
        self, observed_point: type[ObservedPoint], query: Query, since: datetime | None
    ) -> Sequence[FetchedRecord]:
        self.calls.append(FetchCall(observed_point, query, since))
        if self.fail:
            raise RuntimeError("upstream down")
        return [r for r in self.records if since is None or r.occurred_at > since]


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
