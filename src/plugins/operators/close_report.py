"""示例输出类算子：实例关闭时写一份报告草稿。

输出类算子拿到的是只读 BaseContext；写报告的能力由 bootstrap 构造时注入。
"""

from pydantic import BaseModel

from core.contracts import Category, Level, MountPoint, Trigger
from core.operators import BaseContext
from core.report import ReportManager


class CloseReportParams(BaseModel):
    title: str = "子事件收敛"


class CloseReport:
    name = "close_report"
    category: Category = "output"
    levels: frozenset[Level] = frozenset({"instance"})
    mount_points: frozenset[MountPoint] = frozenset({"closed"})
    params_model = CloseReportParams

    def __init__(self, reports: ReportManager) -> None:
        self._reports = reports

    def run(self, trigger: Trigger, ctx: BaseContext) -> None:
        if ctx.parent_id is None:
            return
        params = CloseReportParams.model_validate(ctx.params)
        names = "、".join(ctx.target_names.values()) or "无"
        lines = [f"实例 {ctx.instance_id} 已关闭。", f"涉及目标：{names}", f"最终状态：{ctx.state}"]
        self._reports.write(ctx.parent_id, title=params.title, content="\n".join(lines))
