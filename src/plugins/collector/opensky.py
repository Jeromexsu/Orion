"""示例 Adapter：OpenSky Network 的公开 ADS-B 接口。新增上游照这个写。

一个 Adapter 要回答三件事，全部用类来声明，不写字段名字符串：
- 服务哪个观察点（输出契约）：Position → 返回的 fields 必须能解析成 PositionObservation；
- 支持哪些查询方式（输入契约）：只按 Icao24 查；
- 怎么拉：fetch 把上游的原始响应翻译成 FetchedRecord。

接口说明：https://openskynetwork.github.io/opensky-api/rest.html
GET /states/all?icao24=780a3b 返回该飞机当前的状态向量（只有最新一条，没有历史）。
"""

import json
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any

from core.collector import FetchedRecord, Query
from core.target import ObservedPoint, QueryKey, QuerySpec
from plugins.observed_points.position import Position
from plugins.query_keys.icao24 import Icao24

GetJson = Callable[[str], Any]

API = "https://opensky-network.org/api/states/all"

# 状态向量是数组，按下标取值
_ICAO24, _TIME_POSITION, _LON, _LAT, _BARO_ALT, _ON_GROUND, _GEO_ALT = 0, 3, 5, 6, 7, 8, 13


def _altitude(state: list[Any]) -> float | None:
    """优先几何高度，没有就用气压高度；在地面时报 0。"""
    if state[_ON_GROUND]:
        return 0.0
    return state[_GEO_ALT] if state[_GEO_ALT] is not None else state[_BARO_ALT]


def _http_get_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.load(resp)


class OpenSkyAdapter:
    """按 ICAO 地址查飞机当前位置。"""

    # 普通类属性即可满足 Adapter 协议；不要写 ClassVar（协议里是只读属性，pyright 不认 ClassVar）
    name = "opensky"
    observed_point: type[ObservedPoint] = Position
    query_key_sets: tuple[frozenset[type[QueryKey]], ...] = (frozenset({Icao24}),)

    def __init__(self, get_json: GetJson = _http_get_json) -> None:
        self._get_json = get_json   # 注入点：测试里换成假的，不联网

    def fetch(
        self, spec: QuerySpec, query: Query, since: datetime | None
    ) -> Sequence[FetchedRecord]:
        """查询一次，返回 since 之后的位置。没有位置（刚开机、信号丢失）的状态向量跳过。"""
        icao24 = query[Icao24]   # 已按查询键校验过：6 位小写十六进制
        body = self._get_json(f"{API}?{urllib.parse.urlencode({'icao24': icao24})}")

        records: list[FetchedRecord] = []
        for state in body.get("states") or []:
            if state[_TIME_POSITION] is None or state[_LAT] is None or state[_LON] is None:
                continue
            occurred_at = datetime.fromtimestamp(state[_TIME_POSITION], UTC)
            if since is not None and occurred_at <= since:
                continue
            records.append(
                FetchedRecord(
                    fields={
                        "lat": state[_LAT],
                        "lon": state[_LON],
                        "altitude_m": _altitude(state),
                    },
                    occurred_at=occurred_at,
                    source_id=f"opensky#{state[_ICAO24]}#{state[_TIME_POSITION]}",
                    raw={"state": state},
                )
            )
        return records
