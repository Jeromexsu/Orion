"""报告草稿。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

DRAFT = "草稿"          # 机器可写
EDITING = "编辑中"      # 分析师接手，机器不再写
SENT = "已发出"         # 定稿，任何人不再改
DraftStatus = Literal["草稿", "编辑中", "已发出"]


class Draft(BaseModel):
    """一份报告的当前版本。不可变：每次变更由 ReportManager 生成新对象。"""

    model_config = ConfigDict(frozen=True)

    id: str
    parent_id: str
    title: str
    content: str
    status: DraftStatus
    version: int                # 每次内容变更 +1
    updated_at: datetime
