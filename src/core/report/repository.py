"""report 模块的仓库接口，由 persistence 层实现，bootstrap 时注入。"""

from typing import Protocol

from core.report.draft import Draft


class DraftRepository(Protocol):
    """报告草稿的存取，只存最新版本。"""

    def get(self, draft_id: str) -> Draft | None:
        """不存在返回 None。"""
        ...

    def upsert(self, draft: Draft) -> None:
        """按 id 新建或覆盖。"""
        ...

    def list_by_parent(self, parent_id: str) -> list[Draft]:
        """某个父事件的全部报告。"""
        ...
