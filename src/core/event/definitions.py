"""模板定义（纯数据，前端据此生成表单，存库也存它）。编译后的活对象见 template.py。"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.contracts import ConditionDef, MountPoint


class OperatorMount(BaseModel):
    """在某个挂载点挂一个算子。"""

    model_config = ConfigDict(frozen=True)

    operator: str               # OperatorRegistry 里的算子名
    mount_point: MountPoint
    params: dict[str, Any] = Field(default_factory=dict[str, Any])


class RuleDef(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str                   # 模板内唯一，条件状态按它分组
    condition: ConditionDef
    hooks: list[OperatorMount] = Field(default_factory=list[OperatorMount])  # 只能挂 rule_hit


class TemplateDef(BaseModel):
    """子事件模板定义。不可变：改模板 = 发一个 version 更大的新定义。"""

    model_config = ConfigDict(frozen=True)

    id: str
    version: int = Field(ge=1)
    name: str
    rules: list[RuleDef] = Field(min_length=1)
    # 实例级钩子：created / closed / pre / status_updated / post（rule_hit 挂在规则上）
    hooks: list[OperatorMount] = Field(default_factory=list[OperatorMount])
