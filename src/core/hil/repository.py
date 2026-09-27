"""hil 模块的仓库接口，由 persistence 层实现，bootstrap 时注入。"""

from typing import Protocol

from core.hil.proposal import Proposal


class ProposalRepository(Protocol):
    """提议的存档：待审的和已处理的都保留（已处理的记下是否接受）。"""

    def save(self, proposal: Proposal) -> None:
        """存为待审。"""
        ...

    def get_pending_by_id(self, proposal_id: str) -> Proposal | None:
        """待审的那条；不存在或已处理返回 None。"""
        ...

    def get_pending(self) -> list[Proposal]:
        """全部待审提议。"""
        ...

    def mark_resolved(self, proposal_id: str, accepted: bool) -> None:
        """标记为已处理，记下是否接受。"""
        ...
