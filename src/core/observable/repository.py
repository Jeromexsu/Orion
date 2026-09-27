"""observable 模块的仓库接口，由 persistence 层实现，bootstrap 时注入。"""

from typing import Protocol

from core.observable.observable import ObservableTarget


class ObservableTargetRepository(Protocol):
    """存取可观测目标。key 是可观测目标 ID（`目标ID:观察点名`）。是否保留见 docs/open-questions.md 第 2 条。

    订阅者集合不持久化——重启后由 event 模块重新加载父事件、runner 重新订阅恢复。
    """

    def get(self, key: str) -> ObservableTarget | None:
        """不存在返回 None。"""
        ...

    def upsert(self, observable: ObservableTarget) -> None:
        """按 id 新建或覆盖。"""
        ...

    def remove(self, key: str) -> None:
        """不存在时忽略。"""
        ...

    def list_active(self) -> list[ObservableTarget]:
        """有订阅者的可观测目标。"""
        ...
