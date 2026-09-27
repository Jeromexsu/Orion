"""人在回路：算子提出的操作建议，经分析师确认后才执行。

负责：接收建议（只收白名单动作）→ 待审 → 接受（调用白名单里的核心公开方法）/ 拒绝，并留档。
对外：HilManager（同时实现 operators 的 SuggestionSink）、Suggestion / Proposal、SuggestionRepository。
依赖：无。白名单动作由 bootstrap 用 allow() 注册，hil 不认识任何业务模块。
"""

from core.hil.errors import (
    ActionNotAllowedError,
    DuplicateActionError,
    HilError,
    SuggestionNotFoundError,
)
from core.hil.manager import Action, HilManager
from core.hil.repository import SuggestionRepository
from core.hil.suggestion import Proposal, Suggestion

__all__ = [
    "Action",
    "ActionNotAllowedError",
    "DuplicateActionError",
    "HilError",
    "HilManager",
    "Proposal",
    "Suggestion",
    "SuggestionNotFoundError",
    "SuggestionRepository",
]
