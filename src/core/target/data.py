"""采集相关数据：ObservableTarget 产出 QuerySpec 交给 Adapter；collector 解析出观测、包成 ObservationEnvelope。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, SerializeAsAny

from core.target.observed_point import Observation


class QuerySpec(BaseModel):
    """这次查的是哪个观察点（以及目标类型，仅供兜底）。与上游无关。

    目标的信息只经查询键交给 Adapter（fetch 的 query 参数）：不在查询键范围内的，Adapter 拿不到。
    故意不带目标属性——否则 Adapter 可以绕开查询键按字段名取值，可用性判断也就管不住了。
    """

    model_config = ConfigDict(frozen=True)

    observed_point: str         # 观察点名，如 "position"；Adapter 服务多个观察点时按它分支
    type: str                   # 目标类型。仅供兜底，不推荐依赖：按类型分支意味着新增目标类型要改 Adapter


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
