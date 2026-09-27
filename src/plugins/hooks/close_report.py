"""示例钩子：子事件关闭时写一份报告草稿。只作用于系统外部，照这个写。

也是「一个挂载挂在多处」的示例：挂在规则的 rule_hit 上记下命中，挂在 closed 上把记下的写进报告——
两处共用这个挂载的状态。输出通道（这里是报告）由 bootstrap 构造时注入。
"""

from typing import Any

from pydantic import BaseModel

from core.hooks import ClosedOccasion, Hook, HookContext, Occasion, RuleHitOccasion, hook
from core.report import ReportManager


class CloseReportParams(BaseModel):
    """挂载参数。"""

    title: str = "子事件收敛"


@hook(mount_points={"rule_hit", "closed"}, scopes={"external"})
class CloseReport(Hook[CloseReportParams]):
    """rule_hit：记下命中次数和命中的目标；closed：写一份新草稿到所属父事件。"""

    def __init__(self, report_manager: ReportManager) -> None:
        self._report_manager = report_manager

    def run(
        self, params: CloseReportParams, ctx: HookContext, occasion: Occasion
    ) -> dict[str, Any] | None:
        """Record hits; on close, write a new draft (stored) for the event's parent event."""
        match occasion:
            case RuleHitOccasion(envelope=envelope):
                seen: list[str] = list(ctx.state.get("seen", []))
                name = ctx.target_name(envelope.observable_id)
                if name not in seen:
                    seen.append(name)
                return {"hits": int(ctx.state.get("hits", 0)) + 1, "seen": seen}
            case ClosedOccasion(reason=reason):
                targets = "、".join(ctx.state.get("seen", [])) or "无"
                lines = [
                    f"子事件 {ctx.event_id} 已关闭（{reason}）。",
                    f"命中 {ctx.state.get('hits', 0)} 次，涉及目标：{targets}",
                ]
                self._report_manager.write(
                    ctx.parent_id, title=params.title, content="\n".join(lines)
                )
            case _:
                pass
        return None
