from typing import Any

import pytest
from pydantic import BaseModel

from core.contracts import Proposal, Suggestion, Trigger
from core.operators import (
    BaseContext,
    DuplicateOperatorError,
    InvalidMountError,
    Operator,
    OperatorRegistry,
    ProgressContext,
    SuggestContext,
    UnknownOperatorError,
    build_context,
)
from plugins.operators.count_hits import CountHits


class Recorder:
    def __init__(self) -> None:
        self.patches: list[dict[str, Any]] = []
        self.suggestions: list[Suggestion] = []

    def update_status(self, patch: dict[str, Any]) -> None:
        self.patches.append(patch)

    def suggest(self, item: Suggestion) -> None:
        self.suggestions.append(item)


def ctx_for(category: Any, rec: Recorder, state: dict[str, Any] | None = None, **params: Any) -> BaseContext:
    return build_context(
        category,
        state=state or {},
        params=params,
        target_names={"t1:position": "东航 MU5101"},
        update_status=rec.update_status,
        suggest=rec.suggest,
    )


# ---------------------------------------------------------------- 上下文


def test_context_types_follow_category() -> None:
    rec = Recorder()
    assert type(ctx_for("progress", rec)) is ProgressContext
    assert type(ctx_for("discover", rec)) is SuggestContext
    assert type(ctx_for("calibrate", rec)) is SuggestContext
    assert type(ctx_for("output", rec)) is BaseContext


def test_least_privilege_is_enforced_at_runtime() -> None:
    rec = Recorder()
    output = ctx_for("output", rec)
    with pytest.raises(AttributeError):
        output.update_status({"x": 1})  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        output.suggest(None)  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        ctx_for("discover", rec).update_status({})  # type: ignore[attr-defined]


def test_context_state_is_a_copy() -> None:
    state = {"nested": {"n": 1}}
    ctx = ctx_for("output", Recorder(), state)
    ctx.state["nested"]["n"] = 2
    assert state == {"nested": {"n": 1}}


def test_target_name_falls_back_to_id() -> None:
    ctx = ctx_for("output", Recorder())
    assert ctx.target_name("t1:position") == "东航 MU5101"
    assert ctx.target_name("t9:position") == "t9:position"


def test_output_context_is_serializable() -> None:
    ctx = ctx_for("output", Recorder(), {"hits": 1}, threshold=2)
    assert BaseContext.model_validate_json(ctx.model_dump_json()) == ctx


def test_suggest_context_forwards() -> None:
    rec = Recorder()
    ctx = ctx_for("discover", rec)
    assert isinstance(ctx, SuggestContext)
    item = Suggestion(
        source="alias_finder",
        reason="注册号 B-2447 的新呼号",
        evidence=["adsb#881"],
        proposal=Proposal(action="add_target", target="p1", args={"target_id": "t2"}),
    )
    ctx.suggest(item)
    assert rec.suggestions == [item]


# ---------------------------------------------------------------- 注册表


@pytest.fixture
def registry() -> OperatorRegistry:
    r = OperatorRegistry()
    r.register(CountHits())
    return r


def test_register_and_get(registry: OperatorRegistry) -> None:
    assert registry.get("count_hits").category == "progress"
    with pytest.raises(DuplicateOperatorError):
        registry.register(CountHits())
    with pytest.raises(UnknownOperatorError):
        registry.get("nope")


def test_validate_mount(registry: OperatorRegistry) -> None:
    params = registry.validate_mount("count_hits", "instance", "rule_hit", {"threshold": 3})
    assert params.model_dump() == {"threshold": 3}
    with pytest.raises(InvalidMountError):
        registry.validate_mount("count_hits", "parent", "rule_hit", {})
    with pytest.raises(InvalidMountError):
        registry.validate_mount("count_hits", "instance", "pre", {})
    with pytest.raises(InvalidMountError):
        registry.validate_mount("count_hits", "instance", "rule_hit", {"threshold": 0})


# ---------------------------------------------------------------- 示例算子


def test_count_hits_runs_through_built_context(registry: OperatorRegistry) -> None:
    op = registry.get("count_hits")
    rec = Recorder()
    trigger = Trigger(mount_point="rule_hit")

    op.run(trigger, ctx_for(op.category, rec, {"hits": 0}, threshold=2))
    op.run(trigger, ctx_for(op.category, rec, {"hits": 1}, threshold=2))
    assert rec.patches == [{"hits": 1}, {"hits": 2, "closed": True}]


def test_plugin_satisfies_operator_protocol() -> None:
    op: Operator[ProgressContext] = CountHits()
    assert isinstance(op.params_model(), BaseModel)
