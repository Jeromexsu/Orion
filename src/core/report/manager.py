from datetime import UTC, datetime
from uuid import uuid4

from core.report.errors import ReportLockedError, ReportNotFoundError
from core.report.report import DRAFT, EDITING, SENT, Report
from core.report.repository import ReportRepository


def _now() -> datetime:
    return datetime.now(UTC)


class ReportManager:
    """The life of a report: draft -> (an analyst takes over) editing -> (sent) sent.

    Machine entry points write drafts only: write() and roll(), also offered to hooks as
    ReportWriter. Analyst entry points, called by the API layer: edit() and send().
    """

    def __init__(self, report_repository: ReportRepository) -> None:
        self._report_repository = report_repository

    def get(self, report_id: str) -> Report:
        """Raises ReportNotFoundError if it does not exist."""
        report = self._report_repository.get(report_id)
        if report is None:
            raise ReportNotFoundError(report_id)
        return report

    def list_by_parent(self, parent_id: str) -> list[Report]:
        """Every report of a parent event, in any status."""
        return self._report_repository.list_by_parent(parent_id)

    # ------------------------------------------------------------ machines

    def write(self, parent_id: str, source: str, title: str, content: str) -> Report:
        """Write (store) a new draft."""
        report = Report(
            id=uuid4().hex,
            parent_id=parent_id,
            source=source,
            title=title,
            content=content,
            status=DRAFT,
            version=1,
            updated_at=_now(),
        )
        self._report_repository.upsert(report)
        return report

    def roll(self, parent_id: str, source: str, title: str, content: str) -> Report:
        """Overwrite (store) this source's latest draft under the parent event, version +1.

        Only drafts of the same source are candidates: reports other sources wrote, and
        ones an analyst took over or sent, are never touched. Writes a new draft if there
        is no candidate.
        """
        drafts = [
            r
            for r in self._report_repository.list_by_parent(parent_id)
            if r.source == source and r.status == DRAFT
        ]
        latest = max(drafts, key=lambda r: r.updated_at, default=None)
        if latest is None:
            return self.write(parent_id, source, title, content)
        report = self._bump(latest, title=title, content=content)
        self._report_repository.upsert(report)
        return report

    # ------------------------------------------------------------ analysts

    def edit(self, report_id: str, content: str, title: str | None = None) -> Report:
        """Edit as an analyst (stored): the report becomes "editing" and machines stop
        writing to it.

        Raises:
            ReportLockedError: If it was already sent.
        """
        current = self.get(report_id)
        if current.status == SENT:
            raise ReportLockedError(f"{report_id} was already sent")
        title = title if title is not None else current.title
        report = self._bump(current, title=title, content=content, status=EDITING)
        self._report_repository.upsert(report)
        return report

    def send(self, report_id: str) -> Report:
        """Send it (stored). Nobody can change it afterwards.

        Raises:
            ReportLockedError: If it was already sent.
        """
        current = self.get(report_id)
        if current.status == SENT:
            raise ReportLockedError(f"{report_id} was already sent")
        report = current.model_copy(update={"status": SENT, "updated_at": _now()})
        self._report_repository.upsert(report)
        return report

    @staticmethod
    def _bump(current: Report, **update: object) -> Report:
        return current.model_copy(
            update={**update, "version": current.version + 1, "updated_at": _now()}
        )
