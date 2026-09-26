"""report 模块的仓库接口，由 persistence 层实现，bootstrap 时注入。"""

from typing import Protocol

from core.contracts import Draft


class DraftRepository(Protocol):
    def get(self, draft_id: str) -> Draft | None: ...
    def upsert(self, draft: Draft) -> None: ...
    def list_by_parent(self, parent_id: str) -> list[Draft]: ...
