"""条件定义（纯数据）。结构校验交给 Pydantic，语义校验留给 ConditionCompiler.compile。"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class LeafDef(BaseModel):
    """叶子条件：对一个可观测目标，用一种判断方式、一组参数做判断。"""

    kind: Literal["leaf"] = "leaf"
    observable: str             # 可观测目标 ID，如 "t1:position"
    type: str                   # 判断方式，如 "onEnter"
    params: dict[str, Any] = Field(default_factory=dict[str, Any])  # 由对应的判断方式自己解释


class OpDef(BaseModel):
    """组合条件：all / any / not 组合子条件，三值逻辑见 tree.OpNode。"""

    kind: Literal["op"] = "op"
    op: Literal["all", "any", "not"]
    children: list["ConditionDef"]


ConditionDef = Annotated[LeafDef | OpDef, Field(discriminator="kind")]
OpDef.model_rebuild()
