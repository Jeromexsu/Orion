"""示例推进类算子：规则命中时累加计数，达到阈值时标记收敛（子事件随之关闭）。"""

from pydantic import BaseModel, Field

from core.event import CLOSE_STATUS_KEY
from core.operators import Occasion, Operator, ProgressContext


class CountHitsParams(BaseModel):
    """挂载参数：命中多少次后收敛。"""

    threshold: int = Field(default=1, ge=1)


class CountHits(Operator[ProgressContext]):
    """挂在 rule_hit：状态 hits +1，达到 threshold 时置 CLOSE_STATUS_KEY。"""

    name = "count_hits"
    category = "progress"
    levels = frozenset({"event"})
    mount_points = frozenset({"rule_hit"})
    params_model = CountHitsParams

    def run(self, occasion: Occasion, ctx: ProgressContext) -> None:
        """经 update_status 改子事件状态。"""
        params = CountHitsParams.model_validate(ctx.params)
        hits = int(ctx.state.get("hits", 0)) + 1
        patch: dict[str, object] = {"hits": hits}
        if hits >= params.threshold:
            patch[CLOSE_STATUS_KEY] = True
        ctx.update_status(patch)
