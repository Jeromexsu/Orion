"""目标：Target 基类 / ObservedPoint 观察点 / ObservableTarget / TargetManager。零依赖。"""

from core.target.data import ObservationEnvelope, QuerySpec
from core.target.errors import (
    DuplicateObservedPointError,
    DuplicateTargetTypeError,
    NoUpstreamError,
    TargetError,
    TargetInUseError,
    TargetNotFoundError,
    TargetTypeChangeError,
    UnknownObservedPointError,
    UnknownTargetTypeError,
    UnsupportedObservedPointError,
    UnsupportedUpstreamError,
)
from core.target.manager import TargetManager
from core.target.observable import ObservableTarget, Referencer, observable_key
from core.target.observed_point import Observation, ObservedPoint, observed_point_name
from core.target.repository import ObservableTargetRepository, TargetRepository
from core.target.target import Target, TargetRecord, type_name
from core.target.upstream import UpstreamCatalog

__all__ = [
    "DuplicateObservedPointError",
    "DuplicateTargetTypeError",
    "Observation",
    "ObservationEnvelope",
    "NoUpstreamError",
    "ObservableTarget",
    "ObservableTargetRepository",
    "ObservedPoint",
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
    "UnknownObservedPointError",
    "UnknownTargetTypeError",
    "UnsupportedObservedPointError",
    "UnsupportedUpstreamError",
    "UpstreamCatalog",
    "observable_key",
    "observed_point_name",
    "type_name",
]
