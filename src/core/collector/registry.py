from core.collector.adapter import Adapter
from core.collector.errors import DuplicateAdapterError, UnknownAdapterError
from core.target import ObservedPoint, Target


class AdapterRegistry:
    """Adapter 注册表。结构化地实现 target 的 UpstreamCatalog。"""

    def __init__(self) -> None:
        self._adapters: dict[str, Adapter] = {}

    def register(self, adapter: Adapter) -> None:
        """注册一个上游。名字重复抛 DuplicateAdapterError。"""
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
        return [
            a.name
            for a in self._adapters.values()
            if a.observed_point is observed_point and match_query_fields(a, target) is not None
        ]


def match_query_fields(adapter: Adapter, target: Target) -> frozenset[str] | None:
    """按优先级找出目标满足的第一种查询方式（按字段名匹配，字段须有值）；都不满足返回 None。"""
    values = target.model_dump()
    for fields in adapter.query_field_sets:
        if all(values.get(f) is not None for f in fields):
            return fields
    return None
