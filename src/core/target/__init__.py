"""目标：TargetType / Target / ObservableTarget / TargetManager。零依赖。"""

from core.target.contracts import DynamicData, QuerySpec, Target
from core.target.errors import (
    DuplicateTargetTypeError,
    NoUpstreamError,
    TargetError,
    TargetInUseError,
    TargetNotFoundError,
    TargetTypeChangeError,
    UnknownTargetTypeError,
    UnsupportedFocusError,
)
from core.target.manager import TargetManager
from core.target.observable import ObservableTarget, Referencer, observable_key
from core.target.repository import ObservableTargetRepository, TargetRepository
from core.target.target_type import TargetType
from core.target.upstream import UpstreamCatalog

__all__ = [
    "DuplicateTargetTypeError",
    "DynamicData",
    "NoUpstreamError",
    "ObservableTarget",
    "ObservableTargetRepository",
    "QuerySpec",
    "Referencer",
    "Target",
    "TargetError",
    "TargetInUseError",
    "TargetManager",
    "TargetNotFoundError",
    "TargetRepository",
    "TargetTypeChangeError",
    "TargetType",
    "UnknownTargetTypeError",
    "UnsupportedFocusError",
    "UpstreamCatalog",
    "observable_key",
]
