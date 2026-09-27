from typing import Protocol

from core.report.report import Report


class ReportWriter(Protocol):
    """What machines (hooks, the parent event's digest) may do with reports: write drafts.

    ReportManager implements it structurally. Inject this, not ReportManager, into hooks:
    the analyst's entry points (edit, send) are not theirs to use.
    """

    def write(self, parent_id: str, source: str, title: str, content: str) -> Report:
        """Write a new draft."""
        ...

    def roll(self, parent_id: str, source: str, title: str, content: str) -> Report:
        """Overwrite this source's latest draft under the parent event, or write a new one."""
        ...
