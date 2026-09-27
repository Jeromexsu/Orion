import pytest

from core.report import (
    DRAFT,
    EDITING,
    SENT,
    ReportLockedError,
    ReportManager,
    ReportNotFoundError,
)
from tests.core.report.fakes import InMemoryReportRepository


@pytest.fixture
def reports() -> ReportManager:
    return ReportManager(InMemoryReportRepository())


def test_write_always_creates_a_draft(reports: ReportManager) -> None:
    r1 = reports.write("p1", "closeReport", "告警", "v1")
    r2 = reports.write("p1", "closeReport", "告警", "v2")
    assert (r1.status, r1.version, r1.source) == (DRAFT, 1, "closeReport")
    assert r1.id != r2.id


def test_roll_overwrites_only_its_own_source(reports: ReportManager) -> None:
    other = reports.write("p1", "closeReport", "告警", "x")
    d1 = reports.roll("p1", "digest", "日报", "v1")
    d2 = reports.roll("p1", "digest", "日报", "v2")
    assert (d2.id, d2.version, d2.content) == (d1.id, 2, "v2")
    assert reports.get(other.id) == other          # 别的来源的草稿不碰
    assert reports.roll("p2", "digest", "日报", "v1").id != d1.id   # 别的父事件也不碰


def test_roll_starts_a_new_draft_once_an_analyst_edits(reports: ReportManager) -> None:
    d = reports.roll("p1", "digest", "日报", "machine")
    edited = reports.edit(d.id, "human")
    assert (edited.status, edited.version) == (EDITING, 2)
    again = reports.roll("p1", "digest", "日报", "machine again")
    assert again.id != d.id and reports.get(d.id).content == "human"


def test_send_freezes_the_report(reports: ReportManager) -> None:
    r = reports.write("p1", "digest", "日报", "x")
    sent = reports.send(r.id)
    assert sent.status == SENT and sent.version == r.version
    for action in (lambda: reports.edit(r.id, "y"), lambda: reports.send(r.id)):
        with pytest.raises(ReportLockedError):
            action()


def test_missing_report(reports: ReportManager) -> None:
    with pytest.raises(ReportNotFoundError):
        reports.get("nope")
