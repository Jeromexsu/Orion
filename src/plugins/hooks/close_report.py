"""示例钩子：子事件关闭时写一份报告草稿。只作用于系统外部，照这个写。

输出通道（这里是报告）由 bootstrap 构造时注入；上下文里只有只读信息。
"""

from pydantic import BaseModel

from core.hooks import Hook, HookContext, Occasion, hook
from core.report import ReportManager


class CloseReportParams(BaseModel):
    """挂载参数。"""

    title: str = "子事件收敛"


@hook(mount_points={"closed"}, scopes={"external"})
class CloseReport(Hook[CloseReportParams]):
    """挂在 closed：用子事件最终状态写一份新草稿到所属父事件。"""

    def __init__(self, report_manager: ReportManager) -> None:
        self._report_manager = report_manager

    def run(self, occasion: Occasion, ctx: HookContext[CloseReportParams]) -> None:
        """Write a new draft (stored) for the event's parent event."""
        names = "、".join(ctx.target_names.values()) or "无"
        lines = [f"子事件 {ctx.event_id} 已关闭。", f"涉及目标：{names}", f"最终状态：{ctx.state}"]
        self._report_manager.write(ctx.parent_id, title=ctx.params.title, content="\n".join(lines))
