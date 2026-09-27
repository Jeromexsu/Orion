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

    Adapter 不关心目标类型，只关心观察点和查询所需的字段——不同目标类型只要能提供这些字段，
    就能用同一个 Adapter 观测。
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
    def required_fields(self) -> frozenset[str]:
        """查询需要目标提供的字段（如 icao24）。目标这些字段都有值，才能用这个上游观测它。"""
        ...

    def fetch(self, spec: QuerySpec) -> Sequence[FetchedRecord]:
        """按 spec 拉取 spec.since 之后的记录。"""
        ...
