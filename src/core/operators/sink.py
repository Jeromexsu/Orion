from typing import Protocol

from core.hil import Suggestion


class SuggestionSink(Protocol):
    """建议的去处。由 hil 实现，bootstrap 时注入 event。"""

    def receive(self, suggestion: Suggestion) -> None:
        """接收一条建议（hil 存为待处理）。"""
        ...
