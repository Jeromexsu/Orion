from core.collector.adapter import Adapter, Query, check_adapter
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
        return [
            a.name
            for a in self._adapters.values()
            if observed_point in a.observed_points and match_query(a, target) is not None
        ]


def match_query(adapter: Adapter, target: Target) -> Query | None:
    """按优先级找出目标能提供的第一种查询方式，返回这次的查询（查询键 → 取值）；都不满足返回 None。

    按查询键类匹配，不看字段名；取值在目标构造时已按查询键校验过。
    """
    values = target.query_values()
    for keys in adapter.query_key_sets:
        if keys <= values.keys():
            return {k: values[k] for k in keys}
    return None
