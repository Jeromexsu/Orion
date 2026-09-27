from datetime import UTC, datetime
from uuid import uuid4

from core.report.draft import DRAFT, EDITING, SENT, Draft
from core.report.errors import DraftLockedError, DraftNotFoundError
from core.report.repository import DraftRepository


def _now() -> datetime:
    return datetime.now(UTC)


class ReportManager:
    """报告草稿的生命周期：草稿 →（分析师接手）编辑中 →（发出）已发出。

    write() 是机器入口：只能被报告类钩子或 ParentEvent.digest() 调用，只写“草稿”状态。
    edit() / send() 是分析师入口，由 API 层调用。
    """

    def __init__(self, draft_repository: DraftRepository) -> None:
        self._draft_repository = draft_repository

    def get(self, draft_id: str) -> Draft:
        """不存在抛 DraftNotFoundError。"""
        draft = self._draft_repository.get(draft_id)
        if draft is None:
            raise DraftNotFoundError(draft_id)
        return draft

    def list_by_parent(self, parent_id: str) -> list[Draft]:
        """某个父事件的全部报告（任意状态）。"""
        return self._draft_repository.list_by_parent(parent_id)

    def write(
        self, parent_id: str, title: str, content: str, draft_id: str | None = None
    ) -> Draft:
        """机器写入，返回写入后的草稿（写库）。不给 draft_id 则新建；给了则覆盖内容，版本 +1。

        只允许覆盖本父事件、“草稿”状态的报告，否则抛 DraftLockedError；不存在抛 DraftNotFoundError。
        """
        if draft_id is None:
            draft = Draft(
                id=uuid4().hex,
                parent_id=parent_id,
                title=title,
                content=content,
                status=DRAFT,
                version=1,
                updated_at=_now(),
            )
        else:
            current = self.get(draft_id)
            if current.parent_id != parent_id:
                raise DraftLockedError(f"{draft_id} belongs to {current.parent_id}")
            if current.status != DRAFT:
                raise DraftLockedError(f"{draft_id} is {current.status}; machine writes stop")
            draft = self._bump(current, title=title, content=content)
        self._draft_repository.upsert(draft)
        return draft

    def edit(self, draft_id: str, content: str, title: str | None = None) -> Draft:
        """分析师编辑，返回新版本（写库）：进入“编辑中”，之后机器写入被拒绝。已发出的抛 DraftLockedError。"""
        current = self.get(draft_id)
        if current.status == SENT:
            raise DraftLockedError(f"{draft_id} was already sent")
        draft = self._bump(current, title=title or current.title, content=content, status=EDITING)
        self._draft_repository.upsert(draft)
        return draft

    def send(self, draft_id: str) -> Draft:
        """定稿发出，返回新状态（写库）。之后任何人不能再改；重复发出抛 DraftLockedError。"""
        current = self.get(draft_id)
        if current.status == SENT:
            raise DraftLockedError(f"{draft_id} was already sent")
        draft = current.model_copy(update={"status": SENT, "updated_at": _now()})
        self._draft_repository.upsert(draft)
        return draft

    @staticmethod
    def _bump(current: Draft, **update: object) -> Draft:
        return current.model_copy(
            update={**update, "version": current.version + 1, "updated_at": _now()}
        )
