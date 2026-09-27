from collections.abc import Callable, Mapping
from typing import Any

from core.hil.errors import ActionNotAllowedError, DuplicateActionError, SuggestionNotFoundError
from core.hil.repository import SuggestionRepository
from core.hil.suggestion import Suggestion

# 白名单动作：(proposal.target, 合并后的 args) → 调用对应的核心公开方法
Action = Callable[[str | None, dict[str, Any]], object]


class HilManager:
    """人在回路。结构化地实现 operators 的 SuggestionSink。

    accept() 只能调用白名单里的核心公开方法，这些方法自带完整校验，建议无法绕过。
    白名单由 bootstrap 用 allow() 注册；新增建议来源算子不需要改这里。
    """

    def __init__(self, suggestion_repository: SuggestionRepository) -> None:
        self._suggestion_repository = suggestion_repository
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

    # ------------------------------------------------------------ SuggestionSink

    def receive(self, suggestion: Suggestion) -> None:
        """收下建议待审（写库）。白名单外的 action 抛 ActionNotAllowedError，不让它进审核队列。"""
        if suggestion.proposal.action not in self._actions:
            raise ActionNotAllowedError(
                f"{suggestion.source} proposed {suggestion.proposal.action!r}"
            )
        self._suggestion_repository.save(suggestion)

    # ------------------------------------------------------------ 审核

    def pending(self) -> list[Suggestion]:
        """全部待审建议。"""
        return self._suggestion_repository.get_pending()

    def accept(self, suggestion_id: str, args: Mapping[str, Any] | None = None) -> object:
        """接受建议并执行。args 是分析师在确认前改过的参数，覆盖提议里的同名参数。

        返回白名单方法的返回值；成功后把建议标记为已接受。
        不存在或已处理抛 SuggestionNotFoundError；执行失败（公开方法校验不通过）时异常原样抛出，建议保持待审。
        """
        suggestion = self._pending(suggestion_id)
        handler = self._actions.get(suggestion.proposal.action)
        if handler is None:
            raise ActionNotAllowedError(suggestion.proposal.action)
        result = handler(suggestion.proposal.target, {**suggestion.proposal.args, **(args or {})})
        self._suggestion_repository.mark_resolved(suggestion_id, accepted=True)
        return result

    def reject(self, suggestion_id: str) -> None:
        """拒绝并记录，供以后统计各算子的采纳率。不存在或已处理抛 SuggestionNotFoundError。"""
        self._pending(suggestion_id)
        self._suggestion_repository.mark_resolved(suggestion_id, accepted=False)

    def _pending(self, suggestion_id: str) -> Suggestion:
        suggestion = self._suggestion_repository.get_pending_by_id(suggestion_id)
        if suggestion is None:
            raise SuggestionNotFoundError(suggestion_id)
        return suggestion
