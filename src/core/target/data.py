"""采集相关数据：ObservableTarget 产出 QuerySpec 交给 Adapter；collector 解析出观测、包成 ObservationEnvelope。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SerializeAsAny

from core.target.observed_point import Observation


class QuerySpec(BaseModel):
    """可观测目标对自己的描述：是什么目标、关注哪个观察点、有哪些信息。与上游无关。

    这次用哪种查询方式、从哪个时间点开始拉，是 collector 按上游决定的，不在这里。
    """

    model_config = ConfigDict(frozen=True)

    type: str                   # 目标类型（Adapter 的查询逻辑确实依赖类型时可读它，匹配规则不看它）
    observed_point: str         # 观察点名，如 "position"
    attributes: dict[str, Any]  # 目标全部属性
    aliases: list[str] = Field(default_factory=list[str])


class ObservationEnvelope(BaseModel):
    """观测的外壳：一次观测连同它的来源信息，在采集 → 分发 → 条件判断的管道里流动。collector 产出。"""

    model_config = ConfigDict(frozen=True)

    observable_id: str          # 对哪个 ObservableTarget 的观测
    upstream: str               # 来自哪个上游，ObservableTarget 按它路由给订阅者
    # 具体观测实例（如 PositionObservation），形状由观察点定义；按实际类型序列化
    observation: SerializeAsAny[Observation]
    occurred_at: datetime       # 发生时间（不是处理时间）
    source_id: str              # 去重用，如 "adsb#881"
    raw: dict[str, Any] | None = None  # 上游原始响应，便于排查
