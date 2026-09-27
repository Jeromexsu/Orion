from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from core.target import ObservedPoint, QuerySpec


class FetchedRecord(BaseModel):
    """Adapter 从上游拿到的一条原始记录，尚未按观察点校验。"""

    model_config = ConfigDict(frozen=True)

    fields: dict[str, Any]
    occurred_at: datetime
    source_id: str              # 全局唯一，去重用，如 "adsb#881"
    raw: dict[str, Any] | None = None


class Adapter(Protocol):
    """一个上游一个实现，放在 plugins/collector/ 下。

    Adapter 不关心目标类型，只关心观察点和查询方式——不同目标类型只要能满足其中一种查询方式，
    就能用同一个 Adapter 观测。查询逻辑确实依赖类型时，可在 fetch 里读 QuerySpec.type 兜底。
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
    def query_field_sets(self) -> tuple[frozenset[str], ...]:
        """支持的查询方式，按优先级排列；每种是一组需要目标提供的字段。

        目标满足其中任意一组（这些字段都有值），就能用这个上游观测它；采用第一组满足的，
        取值放进 QuerySpec.query。例如 (frozenset({"icao24"}), frozenset({"mmsi"}))：
        有 ICAO 地址的按它查，有 MMSI 的按它查——Adapter 不需要认识目标类型。
        """
        ...

    def fetch(self, spec: QuerySpec) -> Sequence[FetchedRecord]:
        """按 spec 拉取 spec.since 之后的记录。"""
        ...
