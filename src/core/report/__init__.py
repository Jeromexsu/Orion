"""报告：报告的生命周期。

负责：草稿 →（分析师接手）编辑中 →（发出）已发出；机器只能写“草稿”状态，
      按来源（source）滚动：只覆盖同一来源的最新草稿。
对外：ReportManager（write / roll 给机器、edit / send 给分析师）、ReportWriter（只有机器入口，注入钩子）、
      Report、ReportRepository。
依赖：无。调用方是父事件的 digest() 和报告类钩子。
"""

from core.report.errors import ReportError, ReportLockedError, ReportNotFoundError
from core.report.manager import ReportManager
from core.report.report import DRAFT, EDITING, SENT, Report, ReportStatus
from core.report.repository import ReportRepository
from core.report.writer import ReportWriter

__all__ = [
    "DRAFT",
    "EDITING",
    "Report",
    "ReportError",
    "ReportLockedError",
    "ReportManager",
    "ReportNotFoundError",
    "ReportRepository",
    "ReportStatus",
    "ReportWriter",
    "SENT",
]
