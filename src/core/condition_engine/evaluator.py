"""The evaluator extension point: the Evaluator base class and what it returns (EvalResult)."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any, ClassVar, Generic, Literal, TypeVar, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field

from core.observation import Observation

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
O = TypeVar("O", bound=Observation)


class Evaluator(ABC, Generic[C, O]):
    """一种判断方式（叶子条件）。每种一个子类，放在 plugins/condition_engine/ 下，用 @evaluator 声明：

        @evaluator()
        class OnEnter(Evaluator[OnEnterCriteria, PositionObservation]):
            def evaluate(self, observation, occurred_at, state, criteria): ...

    op 默认是类名首字母小写（OnEnter → "onEnter"）；criteria_model、observation_model 取两个泛型参数。
    判断方式要求一个观测类（不是一串字段名）：模板编译时检查叶子引用的可观测目标产出的观测类是它的子类，
    两边靠 import 同一个类对齐。多个观察点要共用一种判断方式时，把共同的字段提成能力基类，要求那个基类。

    规则：
    - 不得修改传入的 state（只读视图）；新状态放进结果的 state 返回——本叶子的**完整**新状态，
      不是变化量；不变就不填（None）；observation 是副本；
    - 返回“不适用”时不得带 state（带了也会被忽略）。
    """

    op: ClassVar[str]                           # 由 @evaluator 设置；模板里叶子的 op 引用它
    criteria_model: ClassVar[type[BaseModel]]       # 由 @evaluator 设置；判定标准的形状
    observation_model: ClassVar[type[Observation]]  # 由 @evaluator 设置；要求的观测类（或其子类）

    @abstractmethod
    def evaluate(
        self,
        observation: O,
        occurred_at: datetime,
        state: Mapping[str, Any],
        criteria: C,
    ) -> EvalResult:
        """Judge one observation, given this leaf's previous state, against the criteria.

        Gets only what a judgement may depend on: the observation and when it happened.
        Where it came from (upstream, source_id, raw) is deliberately not passed.

        Args:
            observation: The observation (a copy), an instance of observation_model, so
                its fields are typed. An optional field that is None is the evaluator's
                to handle (usually by returning not applicable).
            occurred_at: When the observation happened (not when it was processed).
            state: This leaf's state as last returned (empty on first call); read-only.
                May hold anything (e.g. a sliding window); keep its size bounded.
            criteria: What counts as a hit, as configured in the template and validated
                against criteria_model at compile time.

        Returns:
            The outcome, and in state this leaf's full new state (None if unchanged).
            A not-applicable result must not carry a state.
        """
        ...


E = TypeVar("E", bound=Evaluator[Any, Any])


def evaluator(*, op: str | None = None) -> Callable[[type[E]], type[E]]:
    """Declare an evaluator.

    The criteria model and the required observation class are the two generic arguments
    of the base (Evaluator[OnEnterCriteria, PositionObservation]).

    Args:
        op: Name templates refer to it by. Defaults to the class name with its first
            letter lowered (OnEnter -> "onEnter"); pass it for names starting with an
            acronym.

    Raises:
        TypeError: If the class does not subclass Evaluator[SomeCriteria, SomeObservation].
    """

    def decorate(cls: type[E]) -> type[E]:
        arguments = _generic_arguments(cls)
        if arguments is None:
            raise TypeError(
                f"{cls.__name__}: subclass Evaluator[SomeCriteria, SomeObservation]"
            )
        cls.op = op if op is not None else cls.__name__[:1].lower() + cls.__name__[1:]
        cls.criteria_model, cls.observation_model = arguments
        return cls

    return decorate


def _generic_arguments(cls: type[Any]) -> tuple[type[BaseModel], type[Observation]] | None:
    for base in getattr(cls, "__orig_bases__", ()):
        if get_origin(base) is Evaluator:
            criteria, observation = get_args(base)
            if (
                isinstance(criteria, type)
                and issubclass(criteria, BaseModel)
                and isinstance(observation, type)
                and issubclass(observation, Observation)
            ):
                return criteria, observation
    return None
