from typing import Protocol

from core.hil import Proposal


class ProposalSink(Protocol):
    """提议的去处。由 hil 实现，bootstrap 时注入 event。"""

    def receive(self, proposal: Proposal) -> None:
        """接收一条提议（hil 存为待处理）。"""
        ...
