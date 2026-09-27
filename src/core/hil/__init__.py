"""人在回路：钩子提出的操作提议，经分析师确认后才执行。

负责：接收提议（只收白名单动作，参数按动作的参数模型校验）→ 待审 → 接受（调用白名单里的核心公开方法）/ 拒绝，并留档。
对外：HilManager（同时实现 hooks 的 ProposalSink）、Proposal / ProposalOrigin（来源由钩子上下文填，
      钩子自己不填）、ProposalRepository。
依赖：无。白名单动作由 bootstrap 用 allow() 注册，hil 不认识任何业务模块。
"""

from core.hil.errors import (
    ActionNotAllowedError,
    DuplicateActionError,
    HilError,
    InvalidProposalArgsError,
    ProposalNotFoundError,
)
from core.hil.manager import HilManager
from core.hil.proposal import Proposal, ProposalOrigin
from core.hil.repository import ProposalRepository

__all__ = [
    "ActionNotAllowedError",
    "DuplicateActionError",
    "HilError",
    "HilManager",
    "InvalidProposalArgsError",
    "Proposal",
    "ProposalNotFoundError",
    "ProposalOrigin",
    "ProposalRepository",
]
