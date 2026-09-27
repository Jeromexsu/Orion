"""组合节点三值逻辑的性质测试。"""

from collections.abc import Mapping
from typing import Any, Literal

from hypothesis import given
from hypothesis import strategies as st
from pydantic import BaseModel

from core.condition_engine import (
    HIT,
    MISS,
    NOT_APPLICABLE,
    ConditionEngine,
    EvalResult,
    Evaluator,
    EvaluatorRegistry,
    Outcome,
)
from core.target import ObservationEnvelope
from tests.core.condition_engine.conftest import compile_, make_envelope

outcomes = st.sampled_from([HIT, MISS, NOT_APPLICABLE])


class FixedParams(BaseModel):
    outcome: Literal["命中", "未命中", "不适用"]


class Fixed(Evaluator[FixedParams]):
    type = "fixed"
    requires = frozenset[str]()
    params_model = FixedParams

    def evaluate(
        self, params: FixedParams, envelope: ObservationEnvelope, state: Mapping[str, Any]
    ) -> EvalResult:
        return EvalResult(outcome=params.outcome)


registry = EvaluatorRegistry()
registry.register(Fixed())
engine = ConditionEngine(registry)


def leaf(o: Outcome) -> dict[str, Any]:
    return {"kind": "leaf", "target": "t", "type": "fixed", "params": {"outcome": o}}


def run(definition: dict[str, Any]) -> Outcome:
    return compile_(engine, definition, {"t": set()}).evaluate(make_envelope("t"), {}).outcome


@given(outcomes)
def test_double_negation(o: Outcome) -> None:
    inner = {"kind": "op", "op": "not", "children": [leaf(o)]}
    assert run({"kind": "op", "op": "not", "children": [inner]}) == o


@given(st.lists(outcomes, min_size=1, max_size=6))
def test_de_morgan(xs: list[Outcome]) -> None:
    negated = [{"kind": "op", "op": "not", "children": [leaf(x)]} for x in xs]
    lhs = run({"kind": "op", "op": "not", "children": [{"kind": "op", "op": "all", "children": [leaf(x) for x in xs]}]})
    rhs = run({"kind": "op", "op": "any", "children": negated})
    assert lhs == rhs


@given(st.lists(outcomes, min_size=1, max_size=6))
def test_not_applicable_is_neutral(xs: list[Outcome]) -> None:
    for op in ("all", "any"):
        base = run({"kind": "op", "op": op, "children": [leaf(x) for x in xs]})
        padded = run({"kind": "op", "op": op, "children": [leaf(x) for x in xs] + [leaf(NOT_APPLICABLE)]})
        assert base == padded
