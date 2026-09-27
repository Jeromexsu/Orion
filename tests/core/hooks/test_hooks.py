from datetime import UTC, datetime
from typing import Any

import pytest

from core.condition_engine import HIT, EvalResult
from core.hil import Proposal, ProposalOrigin
from core.hooks import (
    DuplicateHookError,
    EventHandle,
    Hook,
    HookContext,
    HookRegistry,
    MountCompileError,
    MountCompiler,
    MountDef,
    NoParams,
    Occasion,
    RuleHitOccasion,
    UndeclaredCapabilityError,
    UnknownHookError,
    hook,
)
from core.target import ObservationEnvelope
from plugins.hooks.count_hits import CountHits, CountHitsParams
from plugins.observed_points.position import PositionObservation


class FakeEvent:
    """记录经 EventHandle 做的事。"""

    def __init__(self) -> None:
        self.close_reasons: list[str] = []

    def handle(self) -> EventHandle:
        return EventHandle(self.close_reasons.append)


def context(
    state: dict[str, Any] | None = None,
    event: EventHandle | None = None,
    propose: Any = None,
) -> HookContext:
    return HookContext(
        hook_name="countHits",
        mount_name="again",
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
        ctx.event.close("x")
    with pytest.raises(UndeclaredCapabilityError, match="proposes"):
        ctx.propose("add_target", {}, reason="y")


def test_declared_capabilities_reach_the_event_and_the_sink() -> None:
    event = FakeEvent()
    proposals: list[Proposal] = []
    ctx = context(event=event.handle(), propose=proposals.append)

    ctx.event.close("converged")
    ctx.propose("add_target", {"target_id": "t2"}, reason="y", evidence=["adsb#1"])

    assert event.close_reasons == ["converged"]
    (proposal,) = proposals
    assert proposal.origin == ProposalOrigin(
        hook="countHits", mount="again", parent_id="p1", event_id="e1"
    )   # 来源由上下文填，钩子不填
    assert (proposal.action, proposal.args, proposal.evidence) == (
        "add_target", {"target_id": "t2"}, ["adsb#1"]
    )


def test_state_is_a_copy_and_names_fall_back_to_ids() -> None:
    state = {"nested": {"a": 1}}
    ctx = context(state=state)
    ctx.state["nested"]["a"] = 2
    assert state == {"nested": {"a": 1}}
    assert ctx.target_name("t1:position") == "东航 MU5101"
    assert ctx.target_name("t9:position") == "t9:position"


# ---------------------------------------------------------------- 声明


def test_hook_decorator_defaults() -> None:
    assert CountHits.name == "countHits"
    assert CountHits.mount_points == frozenset({"rule_hit"})
    assert CountHits.scopes == frozenset({"event"})
    assert CountHits.proposes is False
    assert CountHits.params_model is CountHitsParams


def test_parent_and_target_scopes_only_through_proposals() -> None:
    for scope in ("parent", "target"):
        with pytest.raises(TypeError, match="through proposals"):

            @hook(mount_points={"pre"}, scopes={scope})  # type: ignore[arg-type]
            class Direct(Hook[NoParams]):  # pyright: ignore[reportUnusedClass]
                def run(self, params: NoParams, ctx: HookContext, occasion: Occasion) -> None:
                    pass


def test_declaration_needs_mount_points() -> None:
    with pytest.raises(TypeError, match="mount_points"):

        @hook(mount_points=[])
        class Nowhere(Hook[NoParams]):  # pyright: ignore[reportUnusedClass]
            def run(self, params: NoParams, ctx: HookContext, occasion: Occasion) -> None:
                pass


# ---------------------------------------------------------------- 注册表


def test_registry() -> None:
    registry = HookRegistry()
    registry.register(CountHits())
    assert isinstance(registry.get("countHits"), CountHits)
    with pytest.raises(DuplicateHookError):
        registry.register(CountHits())
    with pytest.raises(UnknownHookError):
        registry.get("nope")


def test_undeclared_hook_rejected_at_register() -> None:
    class Bare(Hook[NoParams]):
        def run(self, params: NoParams, ctx: HookContext, occasion: Occasion) -> None:
            pass

    with pytest.raises(TypeError, match="@hook"):
        HookRegistry().register(Bare())


# ---------------------------------------------------------------- 挂载


def test_mount_compiles_to_the_hook_with_typed_params() -> None:
    registry = HookRegistry()
    registry.register(CountHits())
    compiler = MountCompiler(registry)

    mount = compiler.compile(
        MountDef(hook="countHits", rules=["enter", "leave"], params={"threshold": 3})
    )
    assert mount.name == "countHits"            # 默认用钩子名
    assert mount.hook is registry.get("countHits")
    assert mount.params == CountHitsParams(threshold=3)
    assert (mount.at, mount.rules) == (frozenset(), {"enter", "leave"})

    for bad, message in [
        (MountDef(hook="nope", rules=["enter"]), "unknown hook"),
        (MountDef(hook="countHits", at=["closed"]), r"cannot mount at \['closed'\]"),
        (MountDef(hook="countHits", at=["rule_hit"]), "list the rules"),
        (MountDef(hook="countHits"), "mounted nowhere"),
        (MountDef(hook="countHits", rules=["enter"], params={"threshold": 0}), "invalid params"),
    ]:
        with pytest.raises(MountCompileError, match=message):
            compiler.compile(bad)


# ---------------------------------------------------------------- 示例钩子


def test_count_hits_counts_and_asks_to_close() -> None:
    count_hits = CountHits()
    event = FakeEvent()
    params = CountHitsParams(threshold=2)

    first = count_hits.run(params, context({}, event.handle()), RULE_HIT)
    assert (first, event.close_reasons) == ({"hits": 1}, [])
    second = count_hits.run(params, context(first, event.handle()), RULE_HIT)
    assert (second, event.close_reasons) == ({"hits": 2}, ["converged"])
