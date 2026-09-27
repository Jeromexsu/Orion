from typing import Any

import pytest
from pydantic import BaseModel

from core.hil import (
    ActionNotAllowedError,
    DuplicateActionError,
    HilManager,
    InvalidProposalArgsError,
    Proposal,
    ProposalNotFoundError,
    ProposalOrigin,
)
from tests.core.hil.fakes import InMemoryProposalRepository

ORIGIN = ProposalOrigin(hook="aliasFinder", mount="aliasFinder", parent_id="p1", event_id="e1")


class AddTargetArgs(BaseModel):
    parent_id: str
    target_id: str
    observed_point: str = "position"


def proposal(action: str = "add_target", **args: Any) -> Proposal:
    return Proposal(
        origin=ORIGIN,
        action=action,
        args={"parent_id": "p1", "target_id": "t2", **args},
        reason="同一注册号出现新呼号",
        evidence=["adsb#881"],
    )


class Env:
    def __init__(self) -> None:
        self.repo = InMemoryProposalRepository()
        self.hil = HilManager(self.repo)
        self.calls: list[AddTargetArgs] = []
        self.hil.allow("add_target", AddTargetArgs, self.add_target)

    def add_target(self, args: AddTargetArgs) -> object:
        if args.observed_point == "invalid":
            raise ValueError("rejected by core validation")
        self.calls.append(args)
        return "ok"


@pytest.fixture
def env() -> Env:
    return Env()


def test_whitelist(env: Env) -> None:
    assert env.hil.allowed_actions() == ["add_target"]
    with pytest.raises(DuplicateActionError):
        env.hil.allow("add_target", AddTargetArgs, env.add_target)


def test_receive_rejects_unknown_actions(env: Env) -> None:
    with pytest.raises(ActionNotAllowedError, match="aliasFinder proposed 'drop_database'"):
        env.hil.receive(proposal("drop_database"))
    assert env.hil.pending() == []


def test_receive_rejects_args_that_do_not_fit_the_action(env: Env) -> None:
    bad = Proposal(origin=ORIGIN, action="add_target", args={"parent_id": "p1"}, reason="x")
    with pytest.raises(InvalidProposalArgsError, match="target_id"):
        env.hil.receive(bad)
    assert env.hil.pending() == []


def test_accept_calls_action_with_typed_args_and_overrides(env: Env) -> None:
    p = proposal()
    env.hil.receive(p)
    assert env.hil.pending() == [p]

    assert env.hil.accept(p.id, {"target_id": "t3"}) == "ok"
    assert env.calls == [AddTargetArgs(parent_id="p1", target_id="t3")]
    assert env.repo.resolved == {p.id: True}
    assert env.hil.pending() == []
    with pytest.raises(ProposalNotFoundError):
        env.hil.accept(p.id)


def test_invalid_overrides_keep_proposal_pending(env: Env) -> None:
    p = proposal()
    env.hil.receive(p)
    with pytest.raises(InvalidProposalArgsError):
        env.hil.accept(p.id, {"target_id": 3})
    assert env.calls == [] and env.hil.pending() == [p]


def test_failed_action_keeps_proposal_pending(env: Env) -> None:
    p = proposal(observed_point="invalid")
    env.hil.receive(p)
    with pytest.raises(ValueError):
        env.hil.accept(p.id)
    assert env.hil.pending() == [p]


def test_reject_is_recorded(env: Env) -> None:
    p = proposal()
    env.hil.receive(p)
    env.hil.reject(p.id)
    assert env.repo.resolved == {p.id: False}
    with pytest.raises(ProposalNotFoundError):
        env.hil.reject(p.id)
