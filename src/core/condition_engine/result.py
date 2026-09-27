"""求值结果。"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

HIT = "命中"
MISS = "未命中"
NOT_APPLICABLE = "不适用"
Outcome = Literal["命中", "未命中", "不适用"]


class EvalResult(BaseModel):
    """一次求值的结果：判断结论 + 附带信息 + 调用方需要保存的新状态。"""

    model_config = ConfigDict(frozen=True)

    # 三值，不是 bool——“不适用”是为了 not/any 不会因为无关数据误判
    outcome: Outcome
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)  # 规则类恒为 1.0
    extracted: dict[str, Any] = Field(default_factory=dict[str, Any])  # 命中的关键词、地点、时间窗口
    trace: list[dict[str, Any]] = Field(default_factory=list[dict[str, Any]])  # 审计/报告引用
    # 只给发起调用的一方保存。树的结果里按节点路径分组：{"root/0": {...}}
    state_patch: dict[str, Any] = Field(default_factory=dict[str, Any])
