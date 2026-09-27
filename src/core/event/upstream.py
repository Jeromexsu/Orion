from collections.abc import Sequence
from typing import Protocol

from core.observation import ObservedPoint
from core.target import Target


class UpstreamCatalog(Protocol):
    """上游目录：模板编译时校验模板里写的上游能不能用。

    由 collector 的 UpstreamAdapterRegistry 结构化实现，bootstrap 时注入 TemplateCompiler
    （event 不依赖 collector）。
    """

    def upstreams_for(self, target: Target, observed_point: type[ObservedPoint]) -> Sequence[str]:
        """能在这个观察点观测这个目标的上游名：服务该观察点，且目标能提供它某种查询方式要的全部查询键。

        按目标当前的查询键现算，不缓存。
        """
        ...
