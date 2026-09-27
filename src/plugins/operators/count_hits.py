"""示例算子：规则命中时累加计数，达到阈值时请求关闭子事件。直接作用于子事件，照这个写。"""

from pydantic import BaseModel, Field

from core.operators import Occasion, Operator, OperatorContext, operator


class CountHitsParams(BaseModel):
    """挂载参数：命中多少次后收敛。"""

    threshold: int = Field(default=1, ge=1)


@operator(mount_points={"rule_hit"}, scopes={"event"})
class CountHits(Operator[CountHitsParams]):
    """挂在 rule_hit：状态 hits +1，达到 threshold 时请求关闭（原因 "converged"）。"""

    def run(self, occasion: Occasion, ctx: OperatorContext[CountHitsParams]) -> None:
        """Count one hit into the event's status; ask to close once the threshold is reached."""
        hits = int(ctx.state.get("hits", 0)) + 1
        ctx.event.update_status({"hits": hits})
        if hits >= ctx.params.threshold:
            ctx.event.close("converged")
