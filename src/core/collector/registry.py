from core.collector.adapter import Adapter
from core.collector.errors import DuplicateAdapterError, UnknownAdapterError


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
    def upstreams_for(self, target_type: str, focus: str) -> list[str]:
        return [a.name for a in self._adapters.values() if (target_type, focus) in a.serves]
