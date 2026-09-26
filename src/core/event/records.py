"""event 的持久化记录（纯数据）。活对象由 EventManager 从这些记录重建。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TargetRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    target_id: str
    focus: str


class TemplateRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    template_id: str
    version: int


class ParentEventRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    targets: list[TargetRef] = Field(default_factory=list[TargetRef])
    templates: list[TemplateRef] = Field(default_factory=list[TemplateRef])


class InstanceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    parent_id: str
    template_id: str
    template_version: int
    status: dict[str, Any]                          # 业务状态，算子可见，只经 update_status 改
    condition_state: dict[str, dict[str, Any]]      # 规则名 → 条件树状态，算子不可见
    opened_at: datetime
    closed_at: datetime | None = None
    close_reason: str | None = None
