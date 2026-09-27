"""Reports and their statuses."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

DRAFT = "草稿"          # 机器可写
EDITING = "编辑中"      # 分析师接手，机器不再写
SENT = "已发出"         # 定稿，任何人不再改
ReportStatus = Literal["草稿", "编辑中", "已发出"]


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
