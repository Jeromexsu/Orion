"""target 模块自己的数据记录。跨模块契约在 core.contracts。"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Target(BaseModel):
    """一个真实实体一条的纯数据记录。"""

    model_config = ConfigDict(frozen=True)

    id: str
    type: str                   # 目标类型名，如 "aircraft"
    name: str                   # 展示名，报告里用
    attributes: dict[str, Any] = Field(default_factory=dict[str, Any])  # 按 TargetType.attributes_model 校验
    aliases: list[str] = Field(default_factory=list[str])
