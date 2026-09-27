"""条件定义（纯数据）。结构校验交给 Pydantic，语义校验留给 ConditionCompiler.compile。

两种节点形状一致：kind 说明是哪种节点，op 说明做什么运算，其余是操作对象。
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class LeafDef(BaseModel):
    """叶子：对一个可观测目标，用一种判断方式按判定标准做判断。"""

    kind: Literal["leaf"] = "leaf"
    op: str                     # 判断方式，如 "onEnter"（Evaluator.op）
    observable: str             # 可观测目标 ID，如 "t1:position"
    criteria: dict[str, Any] = Field(default_factory=dict[str, Any])  # 判定标准，由对应的判断方式解释


class BranchDef(BaseModel):
    """分支：用 all / any / not 组合子条件，三值逻辑见 tree.BranchNode。"""

    kind: Literal["branch"] = "branch"
    op: Literal["all", "any", "not"]
    children: list["ConditionDef"]


ConditionDef = Annotated[LeafDef | BranchDef, Field(discriminator="kind")]
BranchDef.model_rebuild()
