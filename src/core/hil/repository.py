"""hil 模块的仓库接口，由 persistence 层实现，bootstrap 时注入。"""

from typing import Protocol

from core.hil.suggestion import Suggestion


class SuggestionRepository(Protocol):
    """建议的存档：待审的和已处理的都保留（已处理的记下是否接受）。"""

    def save(self, suggestion: Suggestion) -> None:
        """存为待审。"""
        ...

    def get_pending_by_id(self, suggestion_id: str) -> Suggestion | None:
        """待审的那条；不存在或已处理返回 None。"""
        ...

    def get_pending(self) -> list[Suggestion]:
        """全部待审建议。"""
        ...

    def mark_resolved(self, suggestion_id: str, accepted: bool) -> None:
        """标记为已处理，记下是否接受。"""
        ...
