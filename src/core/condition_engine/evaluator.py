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


C = TypeVar("C", bound=BaseModel)


class Evaluator(ABC, Generic[C]):
    """一种判断方式（叶子条件）。每种一个实现，放在 plugins/condition_engine/ 下。

    规则：
    - 不得修改传入的 state（只读视图）；新状态放进结果的 state 返回——本叶子的**完整**新状态，
      不是变化量；不变就不填（None）；envelope 是副本；
    - 返回“不适用”时不得带 state（带了也会被忽略）。
    """

    type: str                   # 模板里引用的名字，如 "onEnter"
    requires: Set[str]          # 需要观测里有值的字段（按字段名，不绑定具体观测类型）
    criteria_model: builtins.type[C]  # 判定标准的形状；类体里的 type 属性遮蔽了内置 type

    @abstractmethod
    def evaluate(
        self, envelope: ObservationEnvelope, state: Mapping[str, Any], criteria: C
    ) -> EvalResult:
        """Judge one observation, given this leaf's previous state, against the criteria.

        The observation is envelope.observation; the fields in requires are guaranteed to
        have values, read them by name (getattr(envelope.observation, "lat")).
        envelope.occurred_at is when it happened. Do not depend on upstream / source_id /
        raw. The envelope is a copy.

        Args:
            envelope: The observation to judge, with its source information.
            state: This leaf's state as last returned (empty on first call); read-only.
                May hold anything (e.g. a sliding window); keep its size bounded.
            criteria: What counts as a hit, as configured in the template and validated
                against criteria_model at compile time.

        Returns:
            The outcome, and in state this leaf's full new state (None if unchanged).
            A not-applicable result must not carry a state.
        """
        ...
