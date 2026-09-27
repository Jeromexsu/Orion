"""示例钩子：规则命中时累加计数，达到阈值时请求关闭子事件。直接作用于子事件，照这个写。"""

from typing import Any

from pydantic import BaseModel, Field

from core.hooks import Hook, HookContext, MountPoint, Occasion, Scope, hook


class CountHitsParams(BaseModel):
    """挂载参数：命中多少次后收敛。"""

    threshold: int = Field(default=1, ge=1)


@hook(mount_points={MountPoint.RULE_HIT}, scopes={Scope.EVENT})
class CountHits(Hook[CountHitsParams]):
    """挂在 rule_hit：自己的状态 hits +1，达到 threshold 时请求关闭（原因 "converged"）。

    计数是这个挂载自己的状态，写它不需要作用域；scopes={"event"} 只为了关闭子事件。
    """

    def run(
        self, params: CountHitsParams, ctx: HookContext, occasion: Occasion
    ) -> dict[str, Any]:
        """Count one hit; ask to close once the threshold is reached."""
        hits = int(ctx.state.get("hits", 0)) + 1
        if hits >= params.threshold:
            ctx.event.close("converged")
        return {"hits": hits}
