"""采集：从上游拉取观测，落库并分发给订阅者。

负责：按可观测目标的活跃上游拉取 → 检查观测类型 → 去重 → 落库 → 推进游标 → 分发。
对外：Collector（定时调用 collect）；AdapterRegistry（注册上游，同时充当 target 的 UpstreamCatalog）；
      Adapter 是上游插件要继承的基类；Query 是交给它的查询（查询键 → 取值）。
依赖：target。
扩展点：plugins/collector/ 下继承 Adapter。
"""

from core.collector.adapter import Adapter, FetchedRecord, Query
from core.collector.collector import Collector
from core.collector.dispatcher import Dispatcher
from core.collector.errors import CollectorError, DuplicateAdapterError, UnknownAdapterError
from core.collector.registry import AdapterRegistry, match_query
from core.collector.repository import CursorRepository, ObservationRepository

__all__ = [
    "Adapter",
    "AdapterRegistry",
    "Collector",
    "CollectorError",
    "CursorRepository",
    "Dispatcher",
    "DuplicateAdapterError",
    "ObservationRepository",
    "FetchedRecord",
    "Query",
    "UnknownAdapterError",
    "match_query",
]
