from core.collector.adapter import Adapter
from core.collector.errors import DuplicateAdapterError, UnknownAdapterError
from core.target import ObservedPoint, Target


class AdapterRegistry:
    """Adapter 注册表。结构化地实现 target 的 UpstreamCatalog。"""

    def __init__(self) -> None:
        self._adapters: dict[str, Adapter] = {}

    def register(self, adapter: Adapter) -> None:
        if adapter.name in self._adapters:
            raise DuplicateAdapterError(adapter.name)
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> Adapter:
        try:
            return self._adapters[name]
        except KeyError:
            raise UnknownAdapterError(name) from None

    def adapters(self) -> list[Adapter]:
        return list(self._adapters.values())

    # UpstreamCatalog
    def upstreams_for(self, target: Target, observed_point: type[ObservedPoint]) -> list[str]:
        """服务该观察点、且查询所需字段目标都有值的上游（按字段名匹配）。"""
        values = target.model_dump()
        return [
            a.name
            for a in self._adapters.values()
            if a.observed_point is observed_point
            and all(values.get(f) is not None for f in a.required_fields)
        ]
