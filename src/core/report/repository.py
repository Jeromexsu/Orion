"""report 模块的仓库接口，由 persistence 层实现，bootstrap 时注入。"""

from typing import Protocol

from core.report.report import Report


class ReportRepository(Protocol):
    """报告的存取，只存最新版本。"""

    def get(self, report_id: str) -> Report | None:
        """不存在返回 None。"""
        ...

    def upsert(self, report: Report) -> None:
        """按 id 新建或覆盖。"""
        ...

    def list_by_parent(self, parent_id: str) -> list[Report]:
        """某个父事件的全部报告。"""
        ...
