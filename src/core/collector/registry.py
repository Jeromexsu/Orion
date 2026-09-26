from core.collector.adapter import Adapter
from core.collector.errors import DuplicateAdapterError, UnknownAdapterError


class AdapterRegistry:
    """Adapter 注册表。结构化地实现 target 的 UpstreamCatalog。"""

    def __init__(self) -> None:
        self._adapter_registry: dict[str, Adapter] = {}

    def register(self, adapter: Adapter) -> None:
        if adapter.name in self._adapter_registry:
            raise DuplicateAdapterError(adapter.name)
        self._adapter_registry[adapter.name] = adapter

    def get(self, name: str) -> Adapter:
        try:
            return self._adapter_registry[name]
        except KeyError:
            raise UnknownAdapterError(name) from None

    def adapters(self) -> list[Adapter]:
        return list(self._adapter_registry.values())

    # UpstreamCatalog
    def upstreams_for(self, target_type: str, focus: str) -> list[str]:
        return [a.name for a in self._adapter_registry.values() if (target_type, focus) in a.serves]
