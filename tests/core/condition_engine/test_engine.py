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
    ConditionEngine,
    DuplicateEvaluatorError,
    EvalResult,
    Evaluator,
    EvaluatorRegistry,
    Observation,
    apply_state_patch,
)
from plugins.condition_engine.on_enter import OnEnter
from tests.core.condition_engine.conftest import (
    SQUARE,
    T0,
    GtParams,
    Obs,
    StaticResolver,
    compile_,
    parse,
)


def enter(target: str = "t1:position", **params: Any) -> dict[str, Any]:
    return {"kind": "leaf", "target": target, "type": "onEnter", "params": {"area": SQUARE, **params}}


def gt(value: float, target: str = "t1:position") -> dict[str, Any]:
    return {"kind": "leaf", "target": target, "type": "gt", "params": {"field": "alt", "value": value}}


def op(name: str, *children: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "op", "op": name, "children": list(children)}


# ---------------------------------------------------------------- 编译


def test_registry_rejects_duplicates() -> None:
    registry = EvaluatorRegistry()
    registry.register(OnEnter())
    with pytest.raises(DuplicateEvaluatorError):
        registry.register(OnEnter())


def test_structure_errors_are_pydantic() -> None:
    with pytest.raises(ValidationError):
        parse({"kind": "op", "op": "and", "children": []})
    with pytest.raises(ValidationError):
        parse({"kind": "leaf", "type": "gt"})


def test_semantic_errors_are_collected_with_paths(engine: ConditionEngine) -> None:
    definition = op(
        "all",
        {"kind": "leaf", "target": "t1:position", "type": "nope"},
        enter(target="ghost"),
        gt(1, target="t2:position"),  # t2 没有 alt
        {"kind": "leaf", "target": "t1:position", "type": "gt", "params": {}},
        op("not", gt(1), gt(2)),
    )
    with pytest.raises(ConditionCompileError) as info:
        compile_(engine, definition)
    errors = info.value.errors
    assert any(e.startswith("root/0: unknown condition type") for e in errors)
    assert any(e.startswith("root/1: unknown target") for e in errors)
    assert any(e.startswith("root/2: target 't2:position' lacks fields ['alt']") for e in errors)
    assert any(e.startswith("root/3: invalid params") for e in errors)
    assert any(e.startswith("root/4: 'not' takes exactly one child") for e in errors)


def test_empty_combinator_rejected(engine: ConditionEngine) -> None:
    with pytest.raises(ConditionCompileError):
        compile_(engine, op("any"))


def test_targets(engine: ConditionEngine) -> None:
    tree = compile_(engine, op("any", enter(), enter(target="t2:position")))
    assert tree.targets() == {"t1:position", "t2:position"}


# ---------------------------------------------------------------- 求值


def test_irrelevant_data_is_not_applicable(engine: ConditionEngine) -> None:
    tree = compile_(engine, op("not", gt(100)))
    assert tree.evaluate(Obs("t2:position", lat=1, lon=1), {}).outcome == NOT_APPLICABLE
    # 字段不全也是不适用
    assert tree.evaluate(Obs("t1:position", lat=1, lon=1), {}).outcome == NOT_APPLICABLE


def test_stateful_leaf_through_state_patch(engine: ConditionEngine) -> None:
    tree = compile_(engine, enter())
    state: dict[str, dict[str, Any]] = {}

    outside = tree.evaluate(Obs("t1:position", lat=20, lon=20), state)
    assert outside.outcome == MISS
    assert outside.state_patch == {"root": {"inside": False}}
    state = apply_state_patch(state, outside.state_patch)

    entered = tree.evaluate(Obs("t1:position", lat=5, lon=5), state)
    assert entered.outcome == HIT
    assert entered.extracted == {"entered_at": {"lat": 5.0, "lon": 5.0}}
    assert entered.trace[0]["fields"] == {"lat": 5, "lon": 5}
    state = apply_state_patch(state, entered.state_patch)

    staying = tree.evaluate(Obs("t1:position", lat=6, lon=6), state)
    assert staying.outcome == MISS


def test_initial_as_enter(engine: ConditionEngine) -> None:
    tree = compile_(engine, enter(initial_as_enter=True))
    assert tree.evaluate(Obs("t1:position", lat=5, lon=5), {}).outcome == HIT


def test_combinators_never_short_circuit(engine: ConditionEngine) -> None:
    # any 的第一个子节点已命中，第二个有状态叶子仍然要更新
    tree = compile_(engine, op("any", gt(0), enter()))
    result = tree.evaluate(Obs("t1:position", lat=5, lon=5, alt=100), {})
    assert result.outcome == HIT
    assert result.state_patch == {"root/1": {"inside": True}}
    assert [t["path"] for t in result.trace] == ["root/0", "root/1"]


def test_not_applicable_is_neutral_in_all(engine: ConditionEngine) -> None:
    tree = compile_(engine, op("all", gt(10), enter(target="t2:position")))
    # 只有 t1 的数据：t2 的叶子不适用，不拖累 all
    result = tree.evaluate(Obs("t1:position", lat=50, lon=50, alt=100), {})
    assert result.outcome == HIT
    assert result.extracted == {"alt": 100}


def test_evaluate_does_not_mutate_state(engine: ConditionEngine) -> None:
    tree = compile_(engine, enter())
    state = {"root": {"inside": False}}
    tree.evaluate(Obs("t1:position", lat=5, lon=5), state)
    assert state == {"root": {"inside": False}}


# ---------------------------------------------------------------- 判断方式拿到的观测


class RecentParams(BaseModel):
    hours: float
    count: int


class RecentCount(Evaluator[RecentParams]):
    """示例：滑动窗口。最近 hours 小时内的观测达到 count 条即命中——状态记的是 N 轮，不只上一轮。"""

    type = "recentCount"
    requires = frozenset({"lat"})
    params_model = RecentParams

    def evaluate(
        self, params: RecentParams, obs: Observation, state: Mapping[str, Any]
    ) -> EvalResult:
        now = obs.occurred_at
        window = [*state.get("window", []), now.isoformat()]
        window = [t for t in window if datetime.fromisoformat(t) > now - timedelta(hours=params.hours)]
        return EvalResult(
            outcome=HIT if len(window) >= params.count else MISS, state_patch={"window": window}
        )


class Spy(Evaluator[GtParams]):
    """记录收到的观测，并尝试篡改它。"""

    type = "spy"
    requires = frozenset({"alt"})
    params_model = GtParams

    def __init__(self) -> None:
        self.seen: list[Observation] = []

    def evaluate(self, params: GtParams, obs: Observation, state: Mapping[str, Any]) -> EvalResult:
        self.seen.append(obs)
        with pytest.raises(TypeError):
            obs.fields["alt"] = 0  # type: ignore[index]
        return EvalResult(outcome=MISS)


def test_evaluator_gets_read_only_observation_with_time() -> None:
    spy = Spy()
    registry = EvaluatorRegistry()
    registry.register(spy)
    engine = ConditionEngine(registry, StaticResolver())
    data = Obs("t1:position", at=3, lat=1, lon=1, alt=100)

    result = compile_(engine, {"kind": "leaf", "target": "t1:position", "type": "spy",
                               "params": {"field": "alt", "value": 0}}).evaluate(data, {})
    (seen,) = spy.seen
    assert seen.occurred_at == T0 + timedelta(hours=3)
    assert data.fields["alt"] == 100
    assert result.trace[0]["occurred_at"] == (T0 + timedelta(hours=3)).isoformat()


def test_state_can_hold_a_sliding_window() -> None:
    registry = EvaluatorRegistry()
    registry.register(RecentCount())
    engine = ConditionEngine(registry, StaticResolver())
    tree = compile_(engine, {"kind": "leaf", "target": "t1:position", "type": "recentCount",
                             "params": {"hours": 24, "count": 3}})

    state: dict[str, dict[str, Any]] = {}
    outcomes: list[str] = []
    for at in (0, 10, 20, 50, 60, 65):  # 小时
        result = tree.evaluate(Obs("t1:position", at=at, lat=1, lon=1, alt=0), state)
        state = apply_state_patch(state, result.state_patch)
        outcomes.append(result.outcome)
    # 第 3 条时 24h 内有 3 条；50h 时窗口只剩它自己；65h 时 50/60/65 三条
    assert outcomes == [MISS, MISS, HIT, MISS, MISS, HIT]
    assert len(state["root"]["window"]) == 3
