"""target 模块对外的数据契约（纯数据、跨 JSON 边界，用 Pydantic）。

DynamicData 由 collector 产出，但定义在这里：它按 ObservableTarget 的
dynamic_schema 校验，且 target 必须零依赖，collector 只能反过来 import 它。
"""

from datetime import datetime
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


class QuerySpec(BaseModel):
    """ObservableTarget 交给 Adapter 的查询说明。"""

    model_config = ConfigDict(frozen=True)

    type: str                   # 目标类型
    focus: str                  # 关注点，如 "position"
    attributes: dict[str, Any]  # 目标属性
    aliases: list[str] = Field(default_factory=list[str])
    since: datetime | None = None


class DynamicData(BaseModel):
    """一条动态数据：判断引擎确认的目标活动发生。"""

    model_config = ConfigDict(frozen=True)

    observable_id: str          # 对应哪个 ObservableTarget
    fields: dict[str, Any]      # 按 dynamic_schema 校验过的字段，如 {"lat": 31.2, "lon": 121.3}
    occurred_at: datetime
    source_id: str              # 去重用，如 "adsb#881"
    raw: dict[str, Any] | None = None  # 上游原始响应，便于排查
