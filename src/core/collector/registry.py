from core.collector.errors import DuplicateUpstreamAdapterError, UnknownUpstreamAdapterError
from core.collector.upstream_adapter import UpstreamAdapter, check_upstream_adapter
from core.target import ObservedPoint, Target


class UpstreamAdapterRegistry:
    """UpstreamAdapter 注册表。结构化地实现 target 的 UpstreamCatalog。"""

    def __init__(self) -> None:
        self._adapters: dict[str, UpstreamAdapter] = {}

    def register(self, adapter: UpstreamAdapter) -> None:
        """注册一个上游。类属性漏写或没有查询方式抛 TypeError；名字重复抛 DuplicateUpstreamAdapterError。"""
        check_upstream_adapter(adapter)
        if adapter.name in self._adapters:
            raise DuplicateUpstreamAdapterError(adapter.name)
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> UpstreamAdapter:
        """上游名 → UpstreamAdapter。未注册抛 UnknownUpstreamAdapterError。"""
        try:
            return self._adapters[name]
        except KeyError:
            raise UnknownUpstreamAdapterError(name) from None

    # UpstreamCatalog
    def upstreams_for(self, target: Target, observed_point: type[ObservedPoint]) -> list[str]:
        """服务该观察点、且目标满足其某种查询方式的上游。"""
        provided = target.query_values()
        return [
            a.name
            for a in self._adapters.values()
            if observed_point in a.observed_points and a.choose_query(provided) is not None
        ]

