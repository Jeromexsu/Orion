"""目标：静态目标、观察点、可观测目标。

负责：目标类型与目标记录；观察点（输出契约：观测的形状）；查询键（输入契约：拿什么去查）；
      可观测目标（目标 + 观察点，全局唯一）及其订阅路由。
对外：TargetManager 是唯一入口；Target / ObservedPoint / Observation / QueryKey 是插件继承的基类；
      ObservationEnvelope 是在管道里流动的观测外壳。
依赖：无（最底层）。上游目录 UpstreamCatalog 由 collector 实现、bootstrap 注入。
扩展点：plugins/target/ 下继承 Target；plugins/observed_points/ 下继承 ObservedPoint + Observation；
        plugins/query_keys/ 下继承 QueryKey。
"""

from core.target.data import ObservationEnvelope
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
from core.target.observable import ObservableTarget, Subscriber, observable_key
from core.target.observed_point import (
    Observation,
    ObservedPoint,
    observed_point,
    observed_point_name,
)
from core.target.query_key import (
    QueryKey,
    provides,
    query_key,
    query_key_name,
    validate_query_value,
)
from core.target.repository import ObservableTargetRepository, TargetRepository
from core.target.target import Target, TargetRecord, target_type, type_name
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
    "QueryKey",
    "Subscriber",
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
    "observed_point",
    "observed_point_name",
    "provides",
    "query_key",
    "query_key_name",
    "target_type",
    "type_name",
    "validate_query_value",
]
