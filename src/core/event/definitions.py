"""模板定义（纯数据，前端据此生成表单，存库也存它）。编译后的活对象见 template.py。

命名约定：纯数据定义的类型以 Def 结尾；装着 Def 的字段以 _def / _defs 结尾——
与运行时对象（如 EventTemplate.open_tree、EventTemplate.rules）一眼能区分。
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.condition_engine import ConditionDef
from core.operators import MountPoint
from core.target import ObservableTarget


class OperatorMountDef(BaseModel):
    """在某个挂载点挂一个算子。"""

    model_config = ConfigDict(frozen=True)

    operator: str               # OperatorRegistry 里的算子名
    mount_point: MountPoint
    params: dict[str, Any] = Field(default_factory=dict[str, Any])


class ObservableDef(BaseModel):
    """可观测目标声明：模板要在哪个观察点观测哪个目标，订阅哪些上游。"""

    model_config = ConfigDict(frozen=True)

    target_id: str              # 必须在父事件的目标命名空间里
    observed_point: str         # 观察点名，如 "position"
    upstreams: list[str] = Field(min_length=1)

    @property
    def observable_id(self) -> str:
        return ObservableTarget.make_id(self.target_id, self.observed_point)


class RuleDef(BaseModel):
    """规则：子事件运行期间，条件命中时跑哪些算子。"""

    model_config = ConfigDict(frozen=True)

    name: str                   # 模板内唯一，条件状态按它分组
    condition_def: ConditionDef
    hook_defs: list[OperatorMountDef] = Field(default_factory=list[OperatorMountDef])  # 只能挂 rule_hit


class TemplateDef(BaseModel):
    """子事件模板定义。不可变：改模板 = 发一个 version 更大的新定义。

    新版本只对下一个周期生效：当前子事件按旧版本跑完，关闭后才切换。
    """

    model_config = ConfigDict(frozen=True)

    id: str
    version: int = Field(ge=1)
    name: str
    observable_defs: list[ObservableDef] = Field(min_length=1)
    # 开启条件：无活跃子事件时命中才开新子事件（runner 在运行期间也持续评估以保持状态最新）
    open_condition_def: ConditionDef
    rule_defs: list[RuleDef] = Field(min_length=1)
    # 子事件级钩子：created / closed / pre / status_updated / post（rule_hit 挂在规则上）
    hook_defs: list[OperatorMountDef] = Field(default_factory=list[OperatorMountDef])

    @property
    def target_ids(self) -> frozenset[str]:
        """可观测目标声明里的静态目标 ID。"""
        return frozenset(o.target_id for o in self.observable_defs)
