"""collector 模块的仓库接口，由 persistence 层实现，bootstrap 时注入。"""

from datetime import datetime
from typing import Protocol

from core.target import ObservationEnvelope


class CursorRepository(Protocol):
    """每个 (ObservableTarget, 上游) 一个游标（ISO 时间戳）：上游之间互不影响，
    某个上游中途才被订阅也不会漏掉它的数据。"""

    def get(self, observable_id: str, upstream: str) -> str | None: ...
    def set(self, observable_id: str, upstream: str, cursor: str) -> None: ...


class ObservationRepository(Protocol):
    def append(self, envelope: ObservationEnvelope) -> None: ...        # 只增不改
    def exists(self, source_id: str) -> bool: ...            # 去重
    def history(
        self, observable_id: str, since: datetime | None = None
    ) -> list[ObservationEnvelope]: ...
