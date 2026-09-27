"""观测外壳：collector 把上游返回的观测包成 ObservationEnvelope，在管道里流动。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, SerializeAsAny

from core.target.observed_point import Observation


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
