from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from core.condition_engine import (
    HIT,
    MISS,
    NOT_APPLICABLE,
    ConditionCompileError,
    ConditionCompiler,
    DuplicateEvaluatorError,
    EvalResult,
    Evaluator,
    EvaluatorRegistry,
    evaluator,
)
from core.target import Observation
from plugins.condition_engine.on_enter import OnEnter
from tests.core.condition_engine.conftest import (
    SQUARE,
    T0,
    GtCriteria,
    compile_,
    make_envelope,
    parse,
)


def enter(observable: str = "t1:position", **criteria: Any) -> dict[str, Any]:
    return {"kind": "leaf", "observable": observable, "op": "onEnter", "criteria": {"area": SQUARE, **criteria}}


def gt(value: float, observable: str = "t1:position") -> dict[str, Any]:
    return {"kind": "leaf", "observable": observable, "op": "gt", "criteria": {"field": "alt", "value": value}}


def op(name: str, *children: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "branch", "op": name, "children": list(children)}


# ---------------------------------------------------------------- 编译


def test_registry_rejects_duplicates() -> None:
    registry = EvaluatorRegistry()
    registry.register(OnEnter())
    with pytest.raises(DuplicateEvaluatorError):
        registry.register(OnEnter())


def test_structure_errors_are_pydantic() -> None:
    with pytest.raises(ValidationError):
        parse({"kind": "branch", "op": "and", "children": []})
    with pytest.raises(ValidationError):
        parse({"kind": "leaf", "op": "gt"})


def test_semantic_errors_are_collected_with_paths(compiler: ConditionCompiler) -> None:
    definition = op(
        "all",
        {"kind": "leaf", "observable": "t1:position", "op": "nope"},
        enter(observable="ghost"),
        gt(1, observable="t2:position"),  # t2 没有 alt
        {"kind": "leaf", "observable": "t1:position", "op": "gt", "criteria": {}},
        op("not", gt(1), gt(2)),
    )
    with pytest.raises(ConditionCompileError) as info:
        compile_(compiler, definition)
    errors = info.value.errors
    assert any(e.startswith("root/0: unknown evaluator op") for e in errors)
    assert any(e.startswith("root/1: unknown observable") for e in errors)
    assert any(e.startswith("root/2: observable 't2:position' lacks fields ['alt']") for e in errors)
    assert any(e.startswith("root/3: invalid criteria") for e in errors)
    assert any(e.startswith("root/4: 'not' takes exactly one child") for e in errors)


def test_empty_combinator_rejected(compiler: ConditionCompiler) -> None:
    with pytest.raises(ConditionCompileError):
        compile_(compiler, op("any"))


# ---------------------------------------------------------------- 求值


def test_irrelevant_data_is_not_applicable(compiler: ConditionCompiler) -> None:
    tree = compile_(compiler, op("not", gt(100)))
    assert tree.evaluate(make_envelope("t2:position", lat=1, lon=1), {}).outcome == NOT_APPLICABLE
    # 字段不全也是不适用
    assert tree.evaluate(make_envelope("t1:position", lat=1, lon=1), {}).outcome == NOT_APPLICABLE


def test_stateful_leaf_returns_new_tree_state(compiler: ConditionCompiler) -> None:
    tree = compile_(compiler, enter())
    state: dict[str, dict[str, Any]] = {}

    outside = tree.evaluate(make_envelope("t1:position", lat=20, lon=20), state)
    assert outside.outcome == MISS
    assert outside.state == {"root": {"inside": False}}
    assert state == {}  # 纯函数：不改入参
    assert outside.state is not None
    state = outside.state

    entered = tree.evaluate(make_envelope("t1:position", lat=5, lon=5), state)
    assert entered.outcome == HIT
    assert entered.extracted == {"entered_at": {"lat": 5.0, "lon": 5.0}}
    assert entered.trace[0]["fields"] == {"lat": 5, "lon": 5}
    assert entered.state == {"root": {"inside": True}}
    assert entered.state is not None
    state = entered.state

    staying = tree.evaluate(make_envelope("t1:position", lat=6, lon=6), state)
    assert staying.outcome == MISS
    assert staying.state is None  # 还在区域内：状态没变


def test_not_applicable_keeps_state(compiler: ConditionCompiler) -> None:
    tree = compile_(compiler, enter())
    state = {"root": {"inside": True}}
    other = tree.evaluate(make_envelope("t2:position", lat=20, lon=20), state)
    assert other.outcome == NOT_APPLICABLE
    assert other.state is None


def test_initial_as_enter(compiler: ConditionCompiler) -> None:
    tree = compile_(compiler, enter(initial_as_enter=True))
    assert tree.evaluate(make_envelope("t1:position", lat=5, lon=5), {}).outcome == HIT


def test_combinators_never_short_circuit(compiler: ConditionCompiler) -> None:
    # any 的第一个子节点已命中，第二个有状态叶子仍然要更新
    tree = compile_(compiler, op("any", gt(0), enter()))
    result = tree.evaluate(make_envelope("t1:position", lat=5, lon=5, alt=100), {})
    assert result.outcome == HIT
    assert result.state == {"root/1": {"inside": True}}
    assert [t["path"] for t in result.trace] == ["root/0", "root/1"]


def test_not_applicable_is_neutral_in_all(compiler: ConditionCompiler) -> None:
    tree = compile_(compiler, op("all", gt(10), enter(observable="t2:position")))
    # 只有 t1 的数据：t2 的叶子不适用，不拖累 all
    result = tree.evaluate(make_envelope("t1:position", lat=50, lon=50, alt=100), {})
    assert result.outcome == HIT
    assert result.extracted == {"alt": 100}


def test_evaluate_does_not_mutate_state(compiler: ConditionCompiler) -> None:
    tree = compile_(compiler, enter())
    state = {"root": {"inside": False}}
    tree.evaluate(make_envelope("t1:position", lat=5, lon=5), state)
    assert state == {"root": {"inside": False}}


# ---------------------------------------------------------------- 判断方式拿到的观测


class RecentCriteria(BaseModel):
    hours: float
    count: int


@evaluator(requires={"lat"})
class RecentCount(Evaluator[RecentCriteria]):
    """示例：滑动窗口。最近 hours 小时内的观测达到 count 条即命中——状态记的是 N 轮，不只上一轮。"""


    def evaluate(
        self,
    observation: Observation,
    occurred_at: datetime,
    state: Mapping[str, Any],
    criteria: RecentCriteria,
) -> EvalResult:
        now = occurred_at
        window = [*state.get("window", []), now.isoformat()]
        window = [t for t in window if datetime.fromisoformat(t) > now - timedelta(hours=criteria.hours)]
        return EvalResult(
            outcome=HIT if len(window) >= criteria.count else MISS, state={"window": window}
        )


@evaluator(requires={"alt"})
class Spy(Evaluator[GtCriteria]):
    """记录收到的观测和发生时间。"""


    def __init__(self) -> None:
        self.seen: list[tuple[Observation, datetime]] = []

    def evaluate(
        self,
    observation: Observation,
    occurred_at: datetime,
    state: Mapping[str, Any],
    criteria: GtCriteria,
) -> EvalResult:
        self.seen.append((observation, occurred_at))
        return EvalResult(outcome=MISS)


def test_evaluator_gets_a_copy_with_time() -> None:
    spy = Spy()
    registry = EvaluatorRegistry()
    registry.register(spy)
    compiler = ConditionCompiler(registry)
    original = make_envelope("t1:position", at=3, lat=1, lon=1, alt=100)

    result = compile_(compiler, {"kind": "leaf", "observable": "t1:position", "op": "spy",
                               "criteria": {"field": "alt", "value": 0}}).evaluate(original, {})
    ((observation, occurred_at),) = spy.seen
    assert occurred_at == T0 + timedelta(hours=3)
    assert observation is not original.observation  # 拿到的是副本
    assert observation == original.observation
    assert result.trace[0]["occurred_at"] == (T0 + timedelta(hours=3)).isoformat()


def test_state_can_hold_a_sliding_window() -> None:
    registry = EvaluatorRegistry()
    registry.register(RecentCount())
    compiler = ConditionCompiler(registry)
    tree = compile_(compiler, {"kind": "leaf", "observable": "t1:position", "op": "recentCount",
                             "criteria": {"hours": 24, "count": 3}})

    state: dict[str, dict[str, Any]] = {}
    outcomes: list[str] = []
    for at in (0, 10, 20, 50, 60, 65):  # 小时
        result = tree.evaluate(make_envelope("t1:position", at=at, lat=1, lon=1, alt=0), state)
        if result.state is not None:
            state = result.state
        outcomes.append(result.outcome)
    # 第 3 条时 24h 内有 3 条；50h 时窗口只剩它自己；65h 时 50/60/65 三条
    assert outcomes == [MISS, MISS, HIT, MISS, MISS, HIT]
    assert len(state["root"]["window"]) == 3


def test_evaluator_decorator_defaults_and_overrides() -> None:
    assert (OnEnter.op, OnEnter.requires, OnEnter.criteria_model.__name__) == (
        "onEnter",
        frozenset({"lat", "lon"}),
        "OnEnterCriteria",
    )

    @evaluator(op="httpCheck")
    class HTTPCheck(Evaluator[GtCriteria]):
        def evaluate(
            self,
        observation: Observation,
        occurred_at: datetime,
        state: Mapping[str, Any],
        criteria: GtCriteria,
    ) -> EvalResult:
            return EvalResult(outcome=MISS)

    assert (HTTPCheck.op, HTTPCheck.requires, HTTPCheck.criteria_model) == (
        "httpCheck",
        frozenset(),
        GtCriteria,
    )


def test_undeclared_evaluator_rejected_at_register() -> None:
    class Bare(Evaluator[GtCriteria]):
        def evaluate(
            self,
        observation: Observation,
        occurred_at: datetime,
        state: Mapping[str, Any],
        criteria: GtCriteria,
    ) -> EvalResult:
            return EvalResult(outcome=MISS)

    with pytest.raises(TypeError, match="@evaluator"):
        EvaluatorRegistry().register(Bare())
