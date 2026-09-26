"""人在回路：HilManager 接收、接受、拒绝 Suggestion。零依赖。"""

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
