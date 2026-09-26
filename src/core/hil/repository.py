"""hil 模块的仓库接口，由 persistence 层实现，bootstrap 时注入。"""

from typing import Protocol

from core.contracts import Suggestion


class SuggestionRepository(Protocol):
    def save(self, suggestion: Suggestion) -> None: ...
    def get_pending_by_id(self, suggestion_id: str) -> Suggestion | None: ...  # 已处理的返回 None
    def get_pending(self) -> list[Suggestion]: ...
    def mark_resolved(self, suggestion_id: str, accepted: bool) -> None: ...
