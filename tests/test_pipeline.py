"""端到端：collector 采集 → Dispatcher → ParentEvent → 条件树 → 推进算子 → 实例收敛。"""

from datetime import UTC, datetime

from core.collector import AdapterRegistry, Collector, Dispatcher, FetchedRecord
from core.event import TemplateDef
from tests.core.collector.fakes import (
    FakeAdapter,
    InMemoryCursorRepository,
    InMemoryDynamicDataRepository,
)
from tests.core.event.conftest import Env, template


def test_collect_drives_sub_event_to_close() -> None:
    env = Env()
    adsb = FakeAdapter("adsb", {("aircraft", "position")})
    adapters = AdapterRegistry()
    adapters.register(adsb)
    collector = Collector(
        env.targets, adapters, InMemoryCursorRepository(), InMemoryDynamicDataRepository(), Dispatcher()
    )

    parent = env.events.create("p1", "东海方向")
    parent.add_target("t1", "position")
    parent.upsert_template(TemplateDef.model_validate(template(threshold=1)))

    adsb.records = [
        FetchedRecord(
            fields={"lat": lat, "lon": lon},
            occurred_at=datetime(2026, 9, 26, 12, minute, tzinfo=UTC),
            source_id=f"adsb#{minute}",
        )
        for minute, (lat, lon) in enumerate([(20, 20), (5, 5)])
    ]
    assert len(collector.collect()) == 2

    (record,) = env.instances.history("p1", "enter-zone")
    assert record.close_reason == "converged"
    assert record.status == {"hits": 1, "closed": True}
