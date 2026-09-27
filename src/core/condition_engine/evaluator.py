"""The evaluator extension point: the Evaluator base class and what it returns (EvalResult)."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping, Set
from typing import Any, ClassVar, Generic, Literal, TypeVar, get_args, get_origin

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
    """一种判断方式（叶子条件）。每种一个子类，放在 plugins/condition_engine/ 下，用 @evaluator 声明：

        @evaluator(requires={"lat", "lon"})
        class OnEnter(Evaluator[OnEnterCriteria]):
            def evaluate(self, envelope, state, criteria): ...

    op 默认是类名首字母小写（OnEnter → "onEnter"）；criteria_model 取泛型参数（OnEnterCriteria）。

    规则：
    - 不得修改传入的 state（只读视图）；新状态放进结果的 state 返回——本叶子的**完整**新状态，
      不是变化量；不变就不填（None）；envelope 是副本；
    - 返回“不适用”时不得带 state（带了也会被忽略）。
    """

    op: ClassVar[str]                           # 由 @evaluator 设置；模板里叶子的 op 引用它
    requires: ClassVar[Set[str]]                # 由 @evaluator 设置；需要观测里有值的字段名
    criteria_model: ClassVar[type[BaseModel]]   # 由 @evaluator 设置；判定标准的形状

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


E = TypeVar("E", bound=Evaluator[Any])


def evaluator(
    *,
    requires: Iterable[str] = (),
    op: str | None = None,
    criteria: type[BaseModel] | None = None,
) -> Callable[[type[E]], type[E]]:
    """Declare an evaluator.

    Args:
        requires: Observation fields that must have a value; otherwise the leaf is not
            applicable and the evaluator is not called.
        op: Name templates refer to it by. Defaults to the class name with its first
            letter lowered (OnEnter -> "onEnter"); pass it for names starting with an
            acronym.
        criteria: The criteria model. Defaults to the generic argument of the base
            (Evaluator[OnEnterCriteria] -> OnEnterCriteria).

    Raises:
        TypeError: If the criteria model can be neither given nor inferred.
    """

    def decorate(cls: type[E]) -> type[E]:
        model = criteria if criteria is not None else _criteria_argument(cls)
        if model is None:
            raise TypeError(
                f"{cls.__name__}: subclass Evaluator[SomeCriteria] or pass criteria=..."
            )
        cls.op = op if op is not None else cls.__name__[:1].lower() + cls.__name__[1:]
        cls.requires = frozenset(requires)
        cls.criteria_model = model
        return cls

    return decorate


def check_evaluator(evaluator: Evaluator[Any]) -> None:
    """Raise TypeError unless the evaluator's class was declared with @evaluator."""
    if not all(hasattr(evaluator, a) for a in ("op", "requires", "criteria_model")):
        raise TypeError(f"{type(evaluator).__name__} must be declared with @evaluator(...)")


def _criteria_argument(cls: type[Any]) -> type[BaseModel] | None:
    for base in getattr(cls, "__orig_bases__", ()):
        if get_origin(base) is Evaluator:
            (argument,) = get_args(base)
            if isinstance(argument, type) and issubclass(argument, BaseModel):
                return argument
    return None
