"""目标：Target 基类 / ObservableTarget / TargetManager。零依赖。"""

from core.target.data import DynamicData, QuerySpec
from core.target.errors import (
    DuplicateTargetTypeError,
    NoUpstreamError,
    TargetError,
    TargetInUseError,
    TargetNotFoundError,
    TargetTypeChangeError,
    UnknownTargetTypeError,
    UnsupportedFocusError,
    UnsupportedUpstreamError,
)
from core.target.manager import TargetManager
from core.target.observable import ObservableTarget, Referencer, observable_key
from core.target.repository import ObservableTargetRepository, TargetRepository
from core.target.target import Target, TargetRecord, type_name
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
    "TargetRecord",
    "TargetRepository",
    "TargetTypeChangeError",
    "UnknownTargetTypeError",
    "UnsupportedFocusError",
    "UnsupportedUpstreamError",
    "UpstreamCatalog",
    "observable_key",
    "type_name",
]
