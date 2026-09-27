from core.collector.adapter import Adapter, check_adapter
from core.collector.errors import DuplicateAdapterError, UnknownAdapterError
from core.target import ObservedPoint, Target


class AdapterRegistry:
    """Adapter 注册表。结构化地实现 target 的 UpstreamCatalog。"""

    def __init__(self) -> None:
        self._adapters: dict[str, Adapter] = {}

    def register(self, adapter: Adapter) -> None:
        """注册一个上游。类属性漏写或没有查询方式抛 TypeError；名字重复抛 DuplicateAdapterError。"""
        check_adapter(adapter)
        if adapter.name in self._adapters:
            raise DuplicateAdapterError(adapter.name)
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> Adapter:
        """上游名 → Adapter。未注册抛 UnknownAdapterError。"""
        try:
            return self._adapters[name]
        except KeyError:
            raise UnknownAdapterError(name) from None

    def adapters(self) -> list[Adapter]:
        """已注册的全部 Adapter。"""
        return list(self._adapters.values())

    # UpstreamCatalog
    def upstreams_for(self, target: Target, observed_point: type[ObservedPoint]) -> list[str]:
        """服务该观察点、且目标满足其某种查询方式的上游。"""
        provided = target.query_values()
        return [
            a.name
            for a in self._adapters.values()
            if observed_point in a.observed_points and a.choose_query(provided) is not None
        ]

