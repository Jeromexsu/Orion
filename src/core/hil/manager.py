from collections.abc import Callable, Mapping
from typing import Any

from core.contracts import Suggestion
from core.hil.errors import ActionNotAllowedError, DuplicateActionError, SuggestionNotFoundError
from core.hil.repository import SuggestionRepository

# 白名单动作：(proposal.target, 合并后的 args) → 调用对应的核心公开方法
Action = Callable[[str | None, dict[str, Any]], object]


class HilManager:
    """人在回路。结构化地实现 operators 的 SuggestionSink。

    accept() 只能调用白名单里的核心公开方法，这些方法自带完整校验，建议无法绕过。
    白名单由 bootstrap 用 allow() 注册；新增建议来源算子不需要改这里。
    """

    def __init__(self, suggestions: SuggestionRepository) -> None:
        self._suggestions = suggestions
        self._actions: dict[str, Action] = {}

    # ------------------------------------------------------------ 白名单

    def allow(self, action: str, handler: Action) -> None:
        if action in self._actions:
            raise DuplicateActionError(action)
        self._actions[action] = handler

    def allowed_actions(self) -> list[str]:
        return sorted(self._actions)

    # ------------------------------------------------------------ SuggestionSink

    def receive(self, suggestion: Suggestion) -> None:
        """收下建议待审。白名单外的 action 直接拒收，不让它进审核队列。"""
        if suggestion.proposal.action not in self._actions:
            raise ActionNotAllowedError(
                f"{suggestion.source} proposed {suggestion.proposal.action!r}"
            )
        self._suggestions.save(suggestion)

    # ------------------------------------------------------------ 审核

    def pending(self) -> list[Suggestion]:
        return self._suggestions.get_pending()

    def accept(self, suggestion_id: str, args: Mapping[str, Any] | None = None) -> object:
        """接受建议并执行。args 是分析师在确认前改过的参数，覆盖提议里的同名参数。

        执行失败（公开方法校验不通过）时异常原样抛出，建议保持待审。
        """
        suggestion = self._pending(suggestion_id)
        handler = self._actions.get(suggestion.proposal.action)
        if handler is None:
            raise ActionNotAllowedError(suggestion.proposal.action)
        result = handler(suggestion.proposal.target, {**suggestion.proposal.args, **(args or {})})
        self._suggestions.mark_resolved(suggestion_id, accepted=True)
        return result

    def reject(self, suggestion_id: str) -> None:
        """拒绝并记录，供以后统计各算子的采纳率。"""
        self._pending(suggestion_id)
        self._suggestions.mark_resolved(suggestion_id, accepted=False)

    def _pending(self, suggestion_id: str) -> Suggestion:
        suggestion = self._suggestions.get_pending_by_id(suggestion_id)
        if suggestion is None:
            raise SuggestionNotFoundError(suggestion_id)
        return suggestion
