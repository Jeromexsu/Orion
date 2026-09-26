from collections.abc import Sequence
from typing import Protocol


class UpstreamCatalog(Protocol):
    """上游目录。由 collector 的 AdapterRegistry 实现，bootstrap 时注入 TargetManager。"""

    def upstreams_for(self, target_type: str, focus: str) -> Sequence[str]:
        """能服务 (target_type, focus) 组合的上游名；没有则返回空。"""
        ...
