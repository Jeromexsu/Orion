from core.report import Report


class InMemoryReportRepository:
    def __init__(self) -> None:
        self.items: dict[str, Report] = {}

    def get(self, report_id: str) -> Report | None:
        return self.items.get(report_id)

    def upsert(self, report: Report) -> None:
        self.items[report.id] = report

    def list_by_parent(self, parent_id: str) -> list[Report]:
        return [r for r in self.items.values() if r.parent_id == parent_id]
