"""collector 模块的仓库接口，由 persistence 层实现，bootstrap 时注入。"""

from datetime import datetime
from typing import Protocol

from core.observation import ObservationEnvelope


class CursorRepository(Protocol):
    """每个 (ObservableTarget, 上游) 一个游标（ISO 时间戳）：上游之间互不影响，
    某个上游中途才被订阅也不会漏掉它的数据。"""

    def get(self, observable_id: str, upstream: str) -> str | None:
        """从未采集过返回 None。"""
        ...

    def set(self, observable_id: str, upstream: str, cursor: str) -> None:
        """覆盖该 (可观测目标, 上游) 的游标。"""
        ...


class ObservationRepository(Protocol):
    """已采集观测的存档，只增不改。读回时的还原见 docs/open-questions.md 第 6 条。"""

    def append(self, envelope: ObservationEnvelope) -> None:
        """追加一条观测。"""
        ...

    def exists(self, source_id: str) -> bool:
        """这个 source_id 是否已存过，collector 用来去重。"""
        ...

    def history(
        self, observable_id: str, since: datetime | None = None
    ) -> list[ObservationEnvelope]:
        """某个可观测目标 since 之后（不含）的观测，按发生时间排序。"""
        ...
