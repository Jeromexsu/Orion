"""采集：从上游拉取观测，落库后经可观测目标发布给订阅者。

负责：按可观测目标的活跃上游拉取 → 检查观测类型 → 去重 → 落库 → 推进游标 → 调用可观测目标的 publish。
对外：Collector（定时调用 collect）；UpstreamAdapterRegistry（注册上游，同时充当 event 的 UpstreamCatalog）；
      UpstreamAdapter 是上游插件要继承的基类（用 @upstream_adapter 声明）；Query 是交给它的查询（查询键 → 取值）。
依赖：observable（活跃的可观测目标）、target（当前目标的查询键）、observation。
扩展点：plugins/upstream_adapters/ 下继承 UpstreamAdapter，用 @upstream_adapter 声明。
"""

from core.collector.collector import Collector
from core.collector.errors import (
    CollectorError,
    DuplicateUpstreamAdapterError,
    UnknownUpstreamAdapterError,
)
from core.collector.registry import UpstreamAdapterRegistry
from core.collector.repository import CursorRepository, ObservationRepository
from core.collector.upstream_adapter import FetchedRecord, Query, UpstreamAdapter, upstream_adapter

__all__ = [
    "UpstreamAdapter",
    "UpstreamAdapterRegistry",
    "upstream_adapter",
    "Collector",
    "CollectorError",
    "CursorRepository",
    "DuplicateUpstreamAdapterError",
    "ObservationRepository",
    "FetchedRecord",
    "Query",
    "UnknownUpstreamAdapterError",
]
