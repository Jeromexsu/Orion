"""采集相关数据：ObservableTarget 产出 QuerySpec 交给 Adapter；collector 按观察点校验后产出 Observation。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class QuerySpec(BaseModel):
    """ObservableTarget 交给 Adapter 的查询说明。"""

    model_config = ConfigDict(frozen=True)

    type: str                   # 目标类型
    observed_point: str         # 观察点名，如 "position"
    attributes: dict[str, Any]  # 目标属性
    aliases: list[str] = Field(default_factory=list[str])
    since: datetime | None = None


class Observation(BaseModel):
    """观测：对一个可观测目标的一次观测结果。collector 产出，条件判断的输入。

    fields 是这次观测的动态数据——形状由观察点（ObservedPoint 子类）定义。
    """

    model_config = ConfigDict(frozen=True)

    observable_id: str          # 对哪个 ObservableTarget 的观测
    upstream: str               # 来自哪个上游，ObservableTarget 按它路由给订阅者
    fields: dict[str, Any]      # 动态数据：按观察点校验过的字段，如 {"lat": 31.2, "lon": 121.3}
    occurred_at: datetime       # 发生时间（不是处理时间）
    source_id: str              # 去重用，如 "adsb#881"
    raw: dict[str, Any] | None = None  # 上游原始响应，便于排查
