"""Reports and their statuses."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ReportStatus(StrEnum):
    """报告的状态：草稿 →（分析师接手）编辑中 →（发出）已发出。"""

    DRAFT = "draft"         # 草稿：机器可写
    EDITING = "editing"     # 编辑中：分析师接手，机器不再写
    SENT = "sent"           # 已发出：定稿，任何人不再改


class Report(BaseModel):
    """The current version of one report. Immutable: ReportManager makes a new one per change."""

    model_config = ConfigDict(frozen=True)

    id: str
    parent_id: str
    source: str                 # who writes it: "digest", or the name of the mount that wrote it
    title: str
    content: str
    status: ReportStatus
    version: int                # +1 on every content change
    updated_at: datetime
