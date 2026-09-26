from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from core.target import QuerySpec


class FetchedRecord(BaseModel):
    """Adapter 从上游拿到的一条原始记录，尚未按 dynamic_schema 校验。"""

    model_config = ConfigDict(frozen=True)

    fields: dict[str, Any]
    occurred_at: datetime
    source_id: str              # 全局唯一，去重用，如 "adsb#881"
    raw: dict[str, Any] | None = None


class Adapter(Protocol):
    """一个上游一个实现，放在 plugins/collector/ 下。"""

    @property
    def name(self) -> str:
        """上游名，写进 ObservableTarget.upstreams。"""
        ...

    @property
    def serves(self) -> frozenset[tuple[str, str]]:
        """能服务的 (target_type, focus) 组合。"""
        ...

    def fetch(self, spec: QuerySpec) -> Sequence[FetchedRecord]:
        """按 spec 拉取 spec.since 之后的记录。"""
        ...
