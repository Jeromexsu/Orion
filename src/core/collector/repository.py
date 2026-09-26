"""collector 模块的仓库接口，由 persistence 层实现，bootstrap 时注入。"""

from datetime import datetime
from typing import Protocol

from core.contracts import DynamicData


class CursorRepository(Protocol):
    def get(self, observable_id: str) -> str | None: ...   # 上次采集游标（ISO 时间戳）
    def set(self, observable_id: str, cursor: str) -> None: ...


class DynamicDataRepository(Protocol):
    def append(self, data: DynamicData) -> None: ...        # 只增不改
    def exists(self, source_id: str) -> bool: ...            # 去重
    def history(
        self, observable_id: str, since: datetime | None = None
    ) -> list[DynamicData]: ...
