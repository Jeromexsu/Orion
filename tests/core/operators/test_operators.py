from datetime import UTC, datetime
from typing import Any

import pytest

from core.condition_engine import HIT, EvalResult
from core.hil import Proposal, Suggestion
from core.operators import (
    DuplicateOperatorError,
    EventHandle,
    NoParams,
    Occasion,
    Operator,
    OperatorContext,
    OperatorRegistry,
    RuleHitOccasion,
    UndeclaredCapabilityError,
    UnknownOperatorError,
    operator,
)
from core.target import ObservationEnvelope
from plugins.observed_points.position import PositionObservation
from plugins.operators.count_hits import CountHits, CountHitsParams


class FakeEvent:
    """记录经 EventHandle 做的事。"""

    def __init__(self) -> None:
        self.patches: list[dict[str, Any]] = []
        self.close_reasons: list[str] = []

    def handle(self) -> EventHandle:
        return EventHandle(self.patches.append, self.close_reasons.append)


def context(
    params: Any = None,
    state: dict[str, Any] | None = None,
    event: EventHandle | None = None,
    propose: Any = None,
) -> OperatorContext[Any]:
    return OperatorContext(
        params=params if params is not None else NoParams(),
        state=state or {},
        target_names={"t1:position": "东航 MU5101"},
        parent_id="p1",
        event_id="e1",
        event=event,
        propose=propose,
    )


RULE_HIT = RuleHitOccasion(
    envelope=ObservationEnvelope(
        observable_id="t1:position",
        upstream="adsb",
        observation=PositionObservation(lat=0, lon=0),
        occurred_at=datetime(2026, 9, 26, tzinfo=UTC),
        source_id="adsb#1",
    ),
    result=EvalResult(outcome=HIT),
)


# ---------------------------------------------------------------- 上下文


def test_undeclared_capabilities_raise() -> None:
    ctx = context()
    with pytest.raises(UndeclaredCapabilityError, match="scopes"):
        ctx.event.update_status({"x": 1})
    with pytest.raises(UndeclaredCapabilityError, match="proposes"):
        ctx.propose(Suggestion(source="x", reason="y", proposal=Proposal(action="add_target")))


def test_declared_capabilities_reach_the_event_and_the_sink() -> None:
    event = FakeEvent()
    proposals: list[Suggestion] = []
    ctx = context(event=event.handle(), propose=proposals.append)

    ctx.event.update_status({"hits": 1})
    ctx.event.close("converged")
    suggestion = Suggestion(source="x", reason="y", proposal=Proposal(action="add_target"))
    ctx.propose(suggestion)

    assert event.patches == [{"hits": 1}]
    assert event.close_reasons == ["converged"]
    assert proposals == [suggestion]


def test_state_is_a_copy_and_names_fall_back_to_ids() -> None:
    state = {"nested": {"a": 1}}
    ctx = context(state=state)
    ctx.state["nested"]["a"] = 2
    assert state == {"nested": {"a": 1}}
    assert ctx.target_name("t1:position") == "东航 MU5101"
    assert ctx.target_name("t9:position") == "t9:position"


# ---------------------------------------------------------------- 声明


def test_operator_decorator_defaults() -> None:
    assert CountHits.name == "countHits"
    assert CountHits.mount_points == frozenset({"rule_hit"})
    assert CountHits.scopes == frozenset({"event"})
    assert CountHits.proposes is False
    assert CountHits.params_model is CountHitsParams


def test_parent_and_target_scopes_only_through_proposals() -> None:
    for scope in ("parent", "target"):
        with pytest.raises(TypeError, match="through proposals"):

            @operator(mount_points={"pre"}, scopes={scope})  # type: ignore[arg-type]
            class Direct(Operator[NoParams]):  # pyright: ignore[reportUnusedClass]
                def run(self, occasion: Occasion, ctx: OperatorContext[NoParams]) -> None:
                    pass


def test_declaration_needs_mount_points() -> None:
    with pytest.raises(TypeError, match="mount_points"):

        @operator(mount_points=[])
        class Nowhere(Operator[NoParams]):  # pyright: ignore[reportUnusedClass]
            def run(self, occasion: Occasion, ctx: OperatorContext[NoParams]) -> None:
                pass


# ---------------------------------------------------------------- 注册表


def test_registry() -> None:
    registry = OperatorRegistry()
    registry.register(CountHits())
    assert isinstance(registry.get("countHits"), CountHits)
    with pytest.raises(DuplicateOperatorError):
        registry.register(CountHits())
    with pytest.raises(UnknownOperatorError):
        registry.get("nope")


def test_undeclared_operator_rejected_at_register() -> None:
    class Bare(Operator[NoParams]):
        def run(self, occasion: Occasion, ctx: OperatorContext[NoParams]) -> None:
            pass

    with pytest.raises(TypeError, match="@operator"):
        OperatorRegistry().register(Bare())


# ---------------------------------------------------------------- 示例算子


def test_count_hits_counts_and_asks_to_close() -> None:
    op = CountHits()
    event = FakeEvent()
    params = CountHitsParams(threshold=2)

    op.run(RULE_HIT, context(params, {"hits": 0}, event.handle()))
    op.run(RULE_HIT, context(params, {"hits": 1}, event.handle()))

    assert event.patches == [{"hits": 1}, {"hits": 2}]
    assert event.close_reasons == ["converged"]
