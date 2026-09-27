"""示例输出类算子：子事件关闭时写一份报告草稿。

输出类算子拿到的是只读 BaseContext；写报告的能力由 bootstrap 构造时注入。
"""

from pydantic import BaseModel

from core.operators import BaseContext, Occasion, Operator
from core.report import ReportManager


class CloseReportParams(BaseModel):
    """挂载参数。"""

    title: str = "子事件收敛"


class CloseReport(Operator[BaseContext]):
    """挂在 closed：用子事件最终状态写一份新草稿到所属父事件。"""

    name = "close_report"
    category = "output"
    levels = frozenset({"event"})
    mount_points = frozenset({"closed"})
    params_model = CloseReportParams

    def __init__(self, report_manager: ReportManager) -> None:
        self._report_manager = report_manager

    def run(self, occasion: Occasion, ctx: BaseContext) -> None:
        """新建一份草稿（写库）。上下文没有父事件 ID 时什么都不做。"""
        if ctx.parent_id is None:
            return
        params = CloseReportParams.model_validate(ctx.params)
        names = "、".join(ctx.target_names.values()) or "无"
        lines = [f"子事件 {ctx.event_id} 已关闭。", f"涉及目标：{names}", f"最终状态：{ctx.state}"]
        self._report_manager.write(ctx.parent_id, title=params.title, content="\n".join(lines))
