from collections.abc import Sequence
from typing import Protocol

from core.target.observed_point import ObservedPoint
from core.target.target import Target


class UpstreamCatalog(Protocol):
    """上游目录。由 collector 的 AdapterRegistry 实现，bootstrap 时注入 TargetManager。"""

    def upstreams_for(self, target: Target, observed_point: type[ObservedPoint]) -> Sequence[str]:
        """能在这个观察点观测这个目标的上游名：服务该观察点，且查询所需字段目标都能提供。"""
        ...
