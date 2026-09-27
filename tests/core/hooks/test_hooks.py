from datetime import UTC, datetime
from typing import Any

import pytest

from core.condition_engine import HIT, EvalResult
from core.hil import Proposal
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
        self.patches: list[dict[str, Any]] = []
        self.close_reasons: list[str] = []

    def handle(self) -> EventHandle:
        return EventHandle(self.patches.append, self.close_reasons.append)


def context(
    params: Any = None,
    state: dict[str, Any] | None = None,
    event: EventHandle | None = None,
    propose: Any = None,
) -> HookContext[Any]:
    return HookContext(
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
        ctx.propose(Proposal(source="x", reason="y", action="add_target"))


def test_declared_capabilities_reach_the_event_and_the_sink() -> None:
    event = FakeEvent()
    proposals: list[Proposal] = []
    ctx = context(event=event.handle(), propose=proposals.append)

    ctx.event.update_status({"hits": 1})
    ctx.event.close("converged")
    proposal = Proposal(source="x", reason="y", action="add_target")
    ctx.propose(proposal)

    assert event.patches == [{"hits": 1}]
    assert event.close_reasons == ["converged"]
    assert proposals == [proposal]


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
                def run(self, occasion: Occasion, ctx: HookContext[NoParams]) -> None:
                    pass


def test_declaration_needs_mount_points() -> None:
    with pytest.raises(TypeError, match="mount_points"):

        @hook(mount_points=[])
        class Nowhere(Hook[NoParams]):  # pyright: ignore[reportUnusedClass]
            def run(self, occasion: Occasion, ctx: HookContext[NoParams]) -> None:
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
        def run(self, occasion: Occasion, ctx: HookContext[NoParams]) -> None:
            pass

    with pytest.raises(TypeError, match="@hook"):
        HookRegistry().register(Bare())


# ---------------------------------------------------------------- 挂载


def test_mount_compiles_to_the_hook_with_typed_params() -> None:
    registry = HookRegistry()
    registry.register(CountHits())
    compiler = MountCompiler(registry)

    mount = compiler.compile(
        MountDef(hook="countHits", mount_point="rule_hit", params={"threshold": 3})
    )
    assert mount.hook is registry.get("countHits")
    assert mount.params == CountHitsParams(threshold=3)

    for bad, message in [
        (MountDef(hook="nope", mount_point="rule_hit"), "unknown hook"),
        (MountDef(hook="countHits", mount_point="closed"), "cannot mount at 'closed'"),
        (
            MountDef(hook="countHits", mount_point="rule_hit", params={"threshold": 0}),
            "invalid params",
        ),
    ]:
        with pytest.raises(MountCompileError, match=message):
            compiler.compile(bad)


# ---------------------------------------------------------------- 示例钩子


def test_count_hits_counts_and_asks_to_close() -> None:
    count_hits = CountHits()
    event = FakeEvent()
    params = CountHitsParams(threshold=2)

    count_hits.run(RULE_HIT, context(params, {"hits": 0}, event.handle()))
    count_hits.run(RULE_HIT, context(params, {"hits": 1}, event.handle()))

    assert event.patches == [{"hits": 1}, {"hits": 2}]
    assert event.close_reasons == ["converged"]
