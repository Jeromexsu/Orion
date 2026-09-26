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


class ObservationDef(BaseModel):
    """观测声明：模板要观测哪个目标的哪个关注点，订阅哪些上游。"""

    model_config = ConfigDict(frozen=True)

    target_id: str              # 必须在父事件的目标命名空间里
    focus: str
    upstreams: list[str] = Field(min_length=1)

    @property
    def observable_id(self) -> str:
        return f"{self.target_id}:{self.focus}"


class RuleDef(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str                   # 模板内唯一，条件状态按它分组
    condition: ConditionDef
    hooks: list[OperatorMount] = Field(default_factory=list[OperatorMount])  # 只能挂 rule_hit


class TemplateDef(BaseModel):
    """子事件模板定义。不可变：改模板 = 发一个 version 更大的新定义。

    新版本只对下一个周期生效：当前子事件按旧版本跑完，关闭后才切换。
    """

    model_config = ConfigDict(frozen=True)

    id: str
    version: int = Field(ge=1)
    name: str
    observations: list[ObservationDef] = Field(min_length=1)
    # 开启条件：无活跃子事件时命中才开新子事件（runner 在运行期间也持续评估以保持状态最新）
    open_condition: ConditionDef
    rules: list[RuleDef] = Field(min_length=1)
    # 子事件级钩子：created / closed / pre / status_updated / post（rule_hit 挂在规则上）
    hooks: list[OperatorMount] = Field(default_factory=list[OperatorMount])
