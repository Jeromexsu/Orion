"""可观测目标：对一个目标在一个观察点上的引用，以及按上游的订阅 / 发布。

负责：可观测目标的单例表（每个 (目标, 观察点) 一个）；按目标当前的查询键现算可用上游；
      订阅者按上游订阅，采集到的观测按上游发布给订阅者。
对外：ObservableTargetManager 是入口；ObservableTarget、Subscriber；UpstreamCatalog（上游目录，由 collector 实现）；
      ObservableTargetRepository。
依赖：target（目标、目标类型注册表）、observation（观察点、观测外壳）。
      结构化地实现 target 的 TargetReferrer，由 bootstrap 接到 TargetManager 上。
"""

from core.observable.errors import (
    NoUpstreamError,
    ObservableError,
    UnsupportedObservedPointError,
    UnsupportedUpstreamError,
)
from core.observable.manager import ObservableTargetManager
from core.observable.observable import ObservableTarget, Subscriber
from core.observable.repository import ObservableTargetRepository
from core.observable.upstream import UpstreamCatalog

__all__ = [
    "NoUpstreamError",
    "ObservableError",
    "ObservableTarget",
    "ObservableTargetManager",
    "ObservableTargetRepository",
    "Subscriber",
    "UnsupportedObservedPointError",
    "UnsupportedUpstreamError",
    "UpstreamCatalog",
]
