"""条件定义（纯数据）。结构校验交给 Pydantic，语义校验留给 ConditionEngine.compile。"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


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
