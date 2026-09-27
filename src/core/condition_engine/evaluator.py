"""The evaluator extension point: the Evaluator base class and what it returns (EvalResult)."""

import builtins
from abc import ABC, abstractmethod
from collections.abc import Mapping, Set
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from core.target import ObservationEnvelope

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


P = TypeVar("P", bound=BaseModel)


class Evaluator(ABC, Generic[P]):
    """一种判断方式（叶子条件）。每种一个实现，放在 plugins/condition_engine/ 下。

    规则：
    - 不得修改传入的 state（只读视图）；新状态放进结果的 state 返回——本叶子的**完整**新状态，
      不是变化量；不变就不填（None）；envelope 是副本；
    - 返回“不适用”时不得带 state（带了也会被忽略）。
    """

    type: str                   # 模板里引用的名字，如 "onEnter"
    requires: Set[str]          # 需要观测里有值的字段（按字段名，不绑定具体观测类型）
    params_model: builtins.type[P]  # 类体里的 type 属性遮蔽了内置 type

    @abstractmethod
    def evaluate(
        self, params: P, envelope: ObservationEnvelope, state: Mapping[str, Any]
    ) -> EvalResult:
        """params：模板里配置、编译时已解析的参数；
        envelope：这一条观测的外壳（副本）。envelope.observation 是观测，requires 里的字段已保证有值，
        按字段名读取（getattr(envelope.observation, "lat")）；envelope.occurred_at 是发生时间；
        判断方式不应依赖 upstream / source_id / raw；
        state：本叶子上次保存的状态（首次为空），可存任意内容（如滑动窗口），需自行控制大小。
        """
        ...
