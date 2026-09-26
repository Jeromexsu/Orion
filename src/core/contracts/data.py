"""采集数据相关契约：target 产出 QuerySpec，collector 产出 DynamicData，下游都消费。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
    upstream: str               # 来自哪个上游，ObservableTarget 按它路由给订阅者
    fields: dict[str, Any]      # 按 dynamic_schema 校验过的字段，如 {"lat": 31.2, "lon": 121.3}
    occurred_at: datetime
    source_id: str              # 去重用，如 "adsb#881"
    raw: dict[str, Any] | None = None  # 上游原始响应，便于排查
