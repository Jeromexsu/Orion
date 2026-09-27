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
    ConditionCompiler,
    EvalResult,
    Evaluator,
    EvaluatorRegistry,
    Outcome,
    evaluator,
)
from core.target import Observation, ObservationEnvelope
from tests.core.condition_engine.conftest import compile_, make_envelope

outcomes = st.sampled_from([HIT, MISS, NOT_APPLICABLE])


class FixedCriteria(BaseModel):
    outcome: Literal["命中", "未命中", "不适用"]


@evaluator()
class Fixed(Evaluator[FixedCriteria]):

    def evaluate(
        self, envelope: ObservationEnvelope, state: Mapping[str, Any], criteria: FixedCriteria
    ) -> EvalResult:
        return EvalResult(outcome=criteria.outcome)


registry = EvaluatorRegistry()
registry.register(Fixed())
compiler = ConditionCompiler(registry)


def leaf(o: Outcome) -> dict[str, Any]:
    return {"kind": "leaf", "observable": "t", "op": "fixed", "criteria": {"outcome": o}}


def run(definition: dict[str, Any]) -> Outcome:
    return compile_(compiler, definition, {"t": Observation}).evaluate(make_envelope("t"), {}).outcome


@given(outcomes)
def test_double_negation(o: Outcome) -> None:
    inner = {"kind": "branch", "op": "not", "children": [leaf(o)]}
    assert run({"kind": "branch", "op": "not", "children": [inner]}) == o


@given(st.lists(outcomes, min_size=1, max_size=6))
def test_de_morgan(xs: list[Outcome]) -> None:
    negated = [{"kind": "branch", "op": "not", "children": [leaf(x)]} for x in xs]
    lhs = run({"kind": "branch", "op": "not", "children": [{"kind": "branch", "op": "all", "children": [leaf(x) for x in xs]}]})
    rhs = run({"kind": "branch", "op": "any", "children": negated})
    assert lhs == rhs


@given(st.lists(outcomes, min_size=1, max_size=6))
def test_not_applicable_is_neutral(xs: list[Outcome]) -> None:
    for op in ("all", "any"):
        base = run({"kind": "branch", "op": op, "children": [leaf(x) for x in xs]})
        padded = run({"kind": "branch", "op": op, "children": [leaf(x) for x in xs] + [leaf(NOT_APPLICABLE)]})
        assert base == padded
