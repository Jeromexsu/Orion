"""target 模块的仓库接口，由 persistence 层实现，bootstrap 时注入。"""

from typing import Protocol

from core.target.observable import ObservableTarget
from core.target.target import TargetRecord


class TargetRepository(Protocol):
    """存取与类型无关的 TargetRecord；还原成具体子类由 TargetManager 负责。"""

    def get(self, target_id: str) -> TargetRecord | None:
        """不存在返回 None。"""
        ...

    def upsert(self, target: TargetRecord) -> None:
        """按 id 新建或覆盖。"""
        ...

    def remove(self, target_id: str) -> None:
        """不存在时忽略。"""
        ...

    def find_by_alias(self, alias: str) -> TargetRecord | None:
        """aliases 里含该别名的目标；没有返回 None。"""
        ...


class ObservableTargetRepository(Protocol):
    """存取可观测目标。key 是可观测目标 ID（`目标ID:观察点名`）。是否保留见 docs/open-questions.md 第 2 条。

    订阅者集合不持久化——重启后由 event 模块重新加载父事件、runner 重新 acquire 恢复。
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
