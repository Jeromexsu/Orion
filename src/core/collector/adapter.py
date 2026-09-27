from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from core.target import ObservedPoint, QueryKey, QuerySpec

Query = dict[type[QueryKey], Any]
"""这次查询：查询键 → 取值，如 {Icao24: "780a3b"}。由 collector 按上游挑出的查询方式组装。"""


class FetchedRecord(BaseModel):
    """Adapter 从上游拿到的一条原始记录，尚未按观察点校验。"""

    model_config = ConfigDict(frozen=True)

    fields: dict[str, Any]
    occurred_at: datetime
    source_id: str              # 全局唯一，去重用，如 "adsb#881"
    raw: dict[str, Any] | None = None


class Adapter(Protocol):
    """一个上游一个实现，放在 plugins/collector/ 下。

    Adapter 不关心目标类型，只关心观察点（输出契约）和查询键（输入契约）——不同目标类型只要
    能提供其中一种查询方式要的查询键，就能用同一个 Adapter 观测。
    查询逻辑确实依赖类型时，可在 fetch 里读 QuerySpec.type 兜底。
    """

    @property
    def name(self) -> str:
        """上游名，写进 ObservableTarget.upstreams。"""
        ...

    @property
    def observed_point(self) -> type[ObservedPoint]:
        """服务的观察点：返回的 FetchedRecord.fields 必须符合它的形状。"""
        ...

    @property
    def query_key_sets(self) -> tuple[frozenset[type[QueryKey]], ...]:
        """支持的查询方式，按优先级排列；每种是一组需要目标提供的查询键。

        目标能提供其中任意一组（这些查询键都有值），就能用这个上游观测它；采用第一组满足的。
        例如 (frozenset({Icao24}), frozenset({Mmsi}))：有 ICAO 地址的按它查，有 MMSI 的按它查——
        Adapter 不需要认识目标类型，也不需要知道目标的字段名。
        """
        ...

    def fetch(
        self, spec: QuerySpec, query: Query, since: datetime | None
    ) -> Sequence[FetchedRecord]:
        """拉取 since 之后（不含）的记录。

        spec：目标自己的描述；query：这次采用的查询方式及取值（已按查询键校验）；
        since：这个上游的游标，首次采集为 None。
        """
        ...
