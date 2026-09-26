"""报告：ReportManager 管理 Draft 的生命周期。零依赖。"""

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
