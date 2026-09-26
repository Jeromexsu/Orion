"""event 的持久化记录（纯数据）。活对象由 EventManager 从这些记录重建。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TemplateRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    template_id: str
    version: int                        # 当前运行的版本
    pending_version: int | None = None  # 已发布、等当前实例关闭后生效的新版本


class ParentEventRecord(BaseModel):
    """父事件是静态的：目标命名空间 + 模板集合。"""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    targets: list[str] = Field(default_factory=list[str])   # 目标命名空间（target_id）
    templates: list[TemplateRef] = Field(default_factory=list[TemplateRef])


class InstanceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    parent_id: str
    template_id: str
    template_version: int
    cycle: int                                      # 周期标识：触发开启的那条数据发生的年份
    status: dict[str, Any]                          # 业务状态，算子可见，只经 update_status 改
    condition_state: dict[str, dict[str, Any]]      # 规则名 → 条件树状态，算子不可见
    opened_at: datetime
    closed_at: datetime | None = None
    close_reason: str | None = None
