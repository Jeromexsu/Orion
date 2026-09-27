"""可观测目标：对一个目标在一个观察点上的引用，以及按上游的订阅 / 发布。

负责：可观测目标的单例表（每个 (目标, 观察点) 一个）；订阅者按上游订阅，采集到的观测按上游发布给订阅者。
      不管上游能不能用：那是模板编译的校验（event 定义的 UpstreamCatalog）。
对外：ObservableTargetFactory 是入口（单例工厂，纯运行时、不存库）；ObservableTarget、Subscriber。
依赖：target（目标）、observation（观察点、观测外壳）。
"""

from core.observable.errors import (
    ObservableError,
    UnsupportedObservedPointError,
    UnsupportedUpstreamError,
)
from core.observable.factory import ObservableTargetFactory
from core.observable.observable import ObservableTarget, Subscriber

__all__ = [
    "ObservableError",
    "ObservableTarget",
    "ObservableTargetFactory",
    "Subscriber",
    "UnsupportedObservedPointError",
    "UnsupportedUpstreamError",
]
