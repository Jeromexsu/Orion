from core.collector.errors import DuplicateUpstreamAdapterError, UnknownUpstreamAdapterError
from core.collector.upstream_adapter import UpstreamAdapter, validate_declaration
from core.observation import ObservedPoint
from core.target import Target


class UpstreamAdapterRegistry:
    """UpstreamAdapter 注册表。结构化地实现 target 的 UpstreamCatalog。"""

    def __init__(self) -> None:
        self._adapters: dict[str, UpstreamAdapter] = {}

    def register(self, adapter: UpstreamAdapter) -> None:
        """注册一个上游。类属性漏写或没有查询方式抛 TypeError；名字重复抛 DuplicateUpstreamAdapterError。"""
        _check_declared(adapter)
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


def _check_declared(adapter: UpstreamAdapter) -> None:
    """Raise TypeError unless the adapter is fully declared (normally by @upstream_adapter)."""
    if not all(hasattr(adapter, a) for a in ("name", "observed_points", "query_key_sets")):
        raise TypeError(f"{type(adapter).__name__} must be declared with @upstream_adapter(...)")
    validate_declaration(
        type(adapter).__name__, adapter.name, adapter.observed_points, adapter.query_key_sets
    )
