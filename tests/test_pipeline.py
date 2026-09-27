"""端到端：collector 采集 → Dispatcher → runner（开启条件）→ 实例（规则 → 推进算子）→ 收敛。"""

from datetime import UTC, datetime

from core.collector import Collector, Dispatcher, FetchedRecord, UpstreamAdapterRegistry
from core.event import TemplateDef
from plugins.observed_points.position import PositionObservation
from tests.core.collector.fakes import (
    FakeUpstreamAdapter,
    InMemoryCursorRepository,
    InMemoryObservationRepository,
)
from tests.core.event.conftest import Env, template


def test_collect_drives_sub_event_to_close() -> None:
    env = Env()
    adsb = FakeUpstreamAdapter("adsb")
    upstream_adapter_registry = UpstreamAdapterRegistry()
    upstream_adapter_registry.register(adsb)
    collector = Collector(
        env.targets,
        upstream_adapter_registry,
        InMemoryCursorRepository(),
        InMemoryObservationRepository(),
        Dispatcher(),
    )

    parent = env.parent_events.create("p1", "东海方向")
    parent.add_target("t1")
    parent.upsert_template(TemplateDef.model_validate(template(threshold=2)))

    adsb.records = [
        FetchedRecord(
            observation=PositionObservation(lat=lat, lon=lon),
            occurred_at=datetime(2026, 9, 26, 12, minute, tzinfo=UTC),
            source_id=f"adsb#{minute}",
        )
        for minute, (lat, lon) in enumerate([(20, 20), (5, 5), (20, 20), (5, 5)])
    ]
    assert len(collector.collect()) == 4

    (record,) = env.events.history("p1", "enter-zone")
    assert record.close_reason == "converged"
    assert record.status == {"hits": 2, "closed": True}
    assert record.cycle == 2026
