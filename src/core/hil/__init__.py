"""人在回路：HilManager 接收、接受、拒绝 Suggestion。只依赖 contracts。"""

from core.hil.errors import (
    ActionNotAllowedError,
    DuplicateActionError,
    HilError,
    SuggestionNotFoundError,
)
from core.hil.manager import Action, HilManager
from core.hil.repository import SuggestionRepository

__all__ = [
    "Action",
    "ActionNotAllowedError",
    "DuplicateActionError",
    "HilError",
    "HilManager",
    "SuggestionNotFoundError",
    "SuggestionRepository",
]
