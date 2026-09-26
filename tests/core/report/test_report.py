import pytest

from core.report import DRAFT, EDITING, SENT, DraftLockedError, DraftNotFoundError, ReportManager
from tests.core.report.fakes import InMemoryDraftRepository


@pytest.fixture
def reports() -> ReportManager:
    return ReportManager(InMemoryDraftRepository())


def test_write_creates_then_overwrites_draft(reports: ReportManager) -> None:
    d1 = reports.write("p1", "日报", "v1")
    assert (d1.status, d1.version) == (DRAFT, 1)
    d2 = reports.write("p1", "日报", "v2", draft_id=d1.id)
    assert (d2.id, d2.version, d2.content) == (d1.id, 2, "v2")
    assert reports.list_by_parent("p1") == [d2]


def test_machine_writes_stop_once_analyst_edits(reports: ReportManager) -> None:
    d = reports.write("p1", "日报", "machine")
    edited = reports.edit(d.id, "human")
    assert (edited.status, edited.version) == (EDITING, 2)
    with pytest.raises(DraftLockedError):
        reports.write("p1", "日报", "machine again", draft_id=d.id)


def test_send_freezes_draft(reports: ReportManager) -> None:
    d = reports.write("p1", "日报", "x")
    sent = reports.send(d.id)
    assert sent.status == SENT and sent.version == d.version
    for action in (lambda: reports.edit(d.id, "y"), lambda: reports.send(d.id)):
        with pytest.raises(DraftLockedError):
            action()


def test_cross_parent_write_rejected(reports: ReportManager) -> None:
    d = reports.write("p1", "日报", "x")
    with pytest.raises(DraftLockedError):
        reports.write("p2", "日报", "y", draft_id=d.id)


def test_missing_draft(reports: ReportManager) -> None:
    with pytest.raises(DraftNotFoundError):
        reports.get("nope")
