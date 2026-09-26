"""算子相关契约。Trigger 可能随异步输出类算子进队列，所以是 Pydantic。"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from core.contracts.condition import EvalResult
from core.contracts.data import DynamicData

# 四类算子：推进（改状态）/ 输出（报告、通知）/ 发现（启发）/ 校正（校准）
Category = Literal["progress", "output", "discover", "calibrate"]

# 可挂的层级：父事件级、实例级
Level = Literal["parent", "instance"]

# 挂载点是核心结构事实，固定这几个：
#   生命周期 created / closed · 数据进入 pre（不算条件，启发算子专用）
#   条件命中 rule_hit · 状态变更后 status_updated · 后置 post
MountPoint = Literal["created", "closed", "pre", "rule_hit", "status_updated", "post"]


class Trigger(BaseModel):
    model_config = ConfigDict(frozen=True)

    mount_point: MountPoint
    data: DynamicData | None = None
    result: EvalResult | None = None
    patch: dict[str, Any] | None = None
