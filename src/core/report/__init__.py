"""报告：报告草稿的生命周期。

负责：草稿 →（分析师接手）编辑中 →（发出）已发出；机器只能写“草稿”状态。
对外：ReportManager（write 给机器、edit / send 给分析师）、Draft、DraftRepository。
依赖：无。调用方是父事件的 digest() 和报告类算子。
"""

from core.report.draft import DRAFT, EDITING, SENT, Draft, DraftStatus
from core.report.errors import DraftLockedError, DraftNotFoundError, ReportError
from core.report.manager import ReportManager
from core.report.repository import DraftRepository

__all__ = [
    "DRAFT",
    "Draft",
    "DraftLockedError",
    "DraftNotFoundError",
    "DraftRepository",
    "DraftStatus",
    "EDITING",
    "ReportError",
    "ReportManager",
    "SENT",
]
