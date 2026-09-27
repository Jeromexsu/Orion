"""人在回路：钩子提出的操作提议，经分析师确认后才执行。

负责：接收提议（只收白名单动作）→ 待审 → 接受（调用白名单里的核心公开方法）/ 拒绝，并留档。
对外：HilManager（同时实现 hooks 的 ProposalSink）、Proposal、ProposalRepository。
依赖：无。白名单动作由 bootstrap 用 allow() 注册，hil 不认识任何业务模块。
"""

from core.hil.errors import (
    ActionNotAllowedError,
    DuplicateActionError,
    HilError,
    ProposalNotFoundError,
)
from core.hil.manager import Action, HilManager
from core.hil.proposal import Proposal
from core.hil.repository import ProposalRepository

__all__ = [
    "Action",
    "ActionNotAllowedError",
    "DuplicateActionError",
    "HilError",
    "HilManager",
    "Proposal",
    "ProposalNotFoundError",
    "ProposalRepository",
]
