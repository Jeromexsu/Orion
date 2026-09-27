from collections.abc import Callable, Mapping
from typing import Any

from core.hil.errors import ActionNotAllowedError, DuplicateActionError, ProposalNotFoundError
from core.hil.proposal import Proposal
from core.hil.repository import ProposalRepository

# 白名单动作：(proposal.target, 合并后的 args) → 调用对应的核心公开方法
Action = Callable[[str | None, dict[str, Any]], object]


class HilManager:
    """人在回路。结构化地实现 hooks 的 ProposalSink。

    accept() 只能调用白名单里的核心公开方法，这些方法自带完整校验，提议无法绕过。
    白名单由 bootstrap 用 allow() 注册；新增提议来源钩子不需要改这里。
    """

    def __init__(self, proposal_repository: ProposalRepository) -> None:
        self._proposal_repository = proposal_repository
        self._actions: dict[str, Action] = {}

    # ------------------------------------------------------------ 白名单

    def allow(self, action: str, handler: Action) -> None:
        """把一个核心公开方法加入白名单。动作名重复抛 DuplicateActionError。"""
        if action in self._actions:
            raise DuplicateActionError(action)
        self._actions[action] = handler

    def allowed_actions(self) -> list[str]:
        """白名单动作名，按字母排序。"""
        return sorted(self._actions)

    # ------------------------------------------------------------ ProposalSink

    def receive(self, proposal: Proposal) -> None:
        """收下提议待审（写库）。白名单外的 action 抛 ActionNotAllowedError，不让它进审核队列。"""
        if proposal.action not in self._actions:
            raise ActionNotAllowedError(
                f"{proposal.source} proposed {proposal.action!r}"
            )
        self._proposal_repository.save(proposal)

    # ------------------------------------------------------------ 审核

    def pending(self) -> list[Proposal]:
        """全部待审提议。"""
        return self._proposal_repository.get_pending()

    def accept(self, proposal_id: str, args: Mapping[str, Any] | None = None) -> object:
        """接受提议并执行。args 是分析师在确认前改过的参数，覆盖提议里的同名参数。

        返回白名单方法的返回值；成功后把提议标记为已接受。
        不存在或已处理抛 ProposalNotFoundError；执行失败（公开方法校验不通过）时异常原样抛出，提议保持待审。
        """
        proposal = self._pending(proposal_id)
        handler = self._actions.get(proposal.action)
        if handler is None:
            raise ActionNotAllowedError(proposal.action)
        result = handler(proposal.target, {**proposal.args, **(args or {})})
        self._proposal_repository.mark_resolved(proposal_id, accepted=True)
        return result

    def reject(self, proposal_id: str) -> None:
        """拒绝并记录，供以后统计各钩子的采纳率。不存在或已处理抛 ProposalNotFoundError。"""
        self._pending(proposal_id)
        self._proposal_repository.mark_resolved(proposal_id, accepted=False)

    def _pending(self, proposal_id: str) -> Proposal:
        proposal = self._proposal_repository.get_pending_by_id(proposal_id)
        if proposal is None:
            raise ProposalNotFoundError(proposal_id)
        return proposal
