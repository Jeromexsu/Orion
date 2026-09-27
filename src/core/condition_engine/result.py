"""求值结果。"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

HIT = "命中"
MISS = "未命中"
NOT_APPLICABLE = "不适用"
Outcome = Literal["命中", "未命中", "不适用"]


class EvalResult(BaseModel):
    """Result of one evaluation: the outcome, extra information and the new state.

    Returned at two levels with the same meaning of state — "the new state of what
    was evaluated; None if unchanged":
    - by an Evaluator (one leaf): the leaf's full new state;
    - by ConditionTree.evaluate: the whole tree's new state.
    """

    model_config = ConfigDict(frozen=True)

    # 三值，不是 bool——“不适用”是为了 not/any 不会因为无关数据误判
    outcome: Outcome
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)  # 规则类恒为 1.0
    extracted: dict[str, Any] = Field(default_factory=dict[str, Any])  # 命中的关键词、地点、时间窗口
    trace: list[dict[str, Any]] = Field(default_factory=list[dict[str, Any]])  # 审计/报告引用
    # 新状态；None = 没变。树的结果里按叶子路径分组：{"root/0": {...}}，由调用方保管
    state: dict[str, Any] | None = None
