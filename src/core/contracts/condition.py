"""condition engine 对外契约。结构校验交给 Pydantic，语义校验留给 ConditionEngine.compile。"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

HIT = "命中"
MISS = "未命中"
NOT_APPLICABLE = "不适用"
Outcome = Literal["命中", "未命中", "不适用"]


class LeafDef(BaseModel):
    kind: Literal["leaf"] = "leaf"
    target: str                 # ObservableTarget 的 ID
    type: str                   # 判断方式，如 "onEnter"
    params: dict[str, Any] = Field(default_factory=dict[str, Any])  # 由对应的判断方式自己解释


class OpDef(BaseModel):
    kind: Literal["op"] = "op"
    op: Literal["all", "any", "not"]
    children: list["ConditionDef"]


ConditionDef = Annotated[LeafDef | OpDef, Field(discriminator="kind")]
OpDef.model_rebuild()


class EvalResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    # 三值，不是 bool——“不适用”是为了 not/any 不会因为无关数据误判
    outcome: Outcome
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)  # 规则类恒为 1.0
    extracted: dict[str, Any] = Field(default_factory=dict[str, Any])  # 命中的关键词、地点、时间窗口
    trace: list[dict[str, Any]] = Field(default_factory=list[dict[str, Any]])  # 审计/报告引用
    # 只给发起调用的子事件保存。树的结果里按节点路径分组：{"root/0": {...}}
    state_patch: dict[str, Any] = Field(default_factory=dict[str, Any])
