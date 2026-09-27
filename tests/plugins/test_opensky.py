from datetime import UTC, datetime
from typing import Any

from core.collector import AdapterRegistry, Collector, Dispatcher
from core.target import QuerySpec, TargetManager
from plugins.collector.opensky import OpenSkyAdapter
from plugins.observed_points.position import PositionObservation
from plugins.query_keys.icao24 import Icao24
from plugins.target.aircraft import Aircraft
from tests.core.collector.fakes import InMemoryCursorRepository, InMemoryObservationRepository
from tests.core.target.conftest import Subscriber
from tests.core.target.fakes import InMemoryObservableTargetRepository, InMemoryTargetRepository

T0 = 1790000000   # Unix 秒


def state(t: int | None, lat: float | None = 31.2, lon: float | None = 121.5) -> list[Any]:
    """一条 OpenSky 状态向量（只填用得到的下标）。"""
    return [
        "780a3b", "CES5101 ", "China", t, t, lon, lat, 9800.0, False,
        230.0, 90.0, 0.0, None, 10050.0, "1234", False, 0,
    ]


class FakeOpenSky:
    """代替网络：记录请求的 URL，返回预设响应。"""

    def __init__(self, *states: list[Any]) -> None:
        self.states = list(states)
        self.urls: list[str] = []

    def __call__(self, url: str) -> Any:
        self.urls.append(url)
        return {"time": T0, "states": self.states}


def test_only_serves_aircraft_with_icao24() -> None:
    registry = AdapterRegistry()
    registry.register(OpenSkyAdapter(FakeOpenSky()))
    with_icao = Aircraft(id="a", name="x", registration="B-1", icao24="780a3b")
    without = Aircraft(id="b", name="y", registration="B-2")
    assert registry.upstreams_for(with_icao, OpenSkyAdapter.observed_point) == ["opensky"]
    assert registry.upstreams_for(without, OpenSkyAdapter.observed_point) == []


def test_fetch_translates_state_vectors() -> None:
    api = FakeOpenSky(state(T0), state(None), state(T0 + 5, lat=None), state(T0 + 10))
    adapter = OpenSkyAdapter(api)
    since = datetime.fromtimestamp(T0, UTC)

    spec = QuerySpec(type="aircraft", observed_point="position", attributes={})
    records = adapter.fetch(spec, {Icao24: "780a3b"}, since)

    assert api.urls == ["https://opensky-network.org/api/states/all?icao24=780a3b"]
    # 没有位置的跳过；since 之前（含）的跳过
    (only,) = records
    assert only.occurred_at == datetime.fromtimestamp(T0 + 10, UTC)
    assert only.fields == {"lat": 31.2, "lon": 121.5, "altitude_m": 10050.0}
    assert only.source_id == f"opensky#780a3b#{T0 + 10}"
    PositionObservation.model_validate(only.fields)   # 符合观察点的形状


def test_collector_end_to_end() -> None:
    """真实的 collector + 这个 Adapter：订阅 → 采集 → 解析 → 分发。"""
    registry = AdapterRegistry()
    registry.register(OpenSkyAdapter(FakeOpenSky(state(T0))))
    manager = TargetManager(
        InMemoryTargetRepository(), InMemoryObservableTargetRepository(), registry
    )
    manager.register_type(Aircraft)
    manager.upsert_target(
        Aircraft(id="t1", name="MU5101", registration="B-2447", icao24="780a3b")
    )
    collector = Collector(
        manager, registry, InMemoryCursorRepository(), InMemoryObservationRepository(), Dispatcher()
    )

    observable = manager.get_observable("t1", "position")
    assert observable.upstreams == ("opensky",)
    sub = Subscriber()
    observable.subscribe(sub, ["opensky"])

    collector.collect()
    (envelope,) = sub.received
    assert envelope.upstream == "opensky"
    assert envelope.observation == PositionObservation(lat=31.2, lon=121.5, altitude_m=10050.0)

    collector.collect()   # 上游还是同一条：游标挡住，不重复分发
    assert len(sub.received) == 1
