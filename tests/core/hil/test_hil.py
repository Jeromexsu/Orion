from typing import Any

import pytest

from core.hil import (
    ActionNotAllowedError,
    DuplicateActionError,
    HilManager,
    Proposal,
    Suggestion,
    SuggestionNotFoundError,
)
from tests.core.hil.fakes import InMemorySuggestionRepository


def suggestion(action: str = "add_target", **args: Any) -> Suggestion:
    return Suggestion(
        source="alias_finder",
        reason="同一注册号出现新呼号",
        evidence=["adsb#881"],
        proposal=Proposal(action=action, target="p1", args=args),
    )


class Env:
    def __init__(self) -> None:
        self.repo = InMemorySuggestionRepository()
        self.hil = HilManager(self.repo)
        self.calls: list[tuple[str | None, dict[str, Any]]] = []
        self.hil.allow("add_target", self.add_target)

    def add_target(self, target: str | None, args: dict[str, Any]) -> object:
        if args.get("focus") == "invalid":
            raise ValueError("rejected by core validation")
        self.calls.append((target, args))
        return "ok"


@pytest.fixture
def env() -> Env:
    return Env()


def test_whitelist(env: Env) -> None:
    assert env.hil.allowed_actions() == ["add_target"]
    with pytest.raises(DuplicateActionError):
        env.hil.allow("add_target", env.add_target)


def test_receive_rejects_unknown_actions(env: Env) -> None:
    with pytest.raises(ActionNotAllowedError):
        env.hil.receive(suggestion("drop_database"))
    assert env.hil.pending() == []


def test_accept_calls_action_with_analyst_overrides(env: Env) -> None:
    s = suggestion(target_id="t2", focus="position")
    env.hil.receive(s)
    assert env.hil.pending() == [s]

    assert env.hil.accept(s.id, {"target_id": "t3"}) == "ok"
    assert env.calls == [("p1", {"target_id": "t3", "focus": "position"})]
    assert env.repo.resolved == {s.id: True}
    assert env.hil.pending() == []
    with pytest.raises(SuggestionNotFoundError):
        env.hil.accept(s.id)


def test_failed_action_keeps_suggestion_pending(env: Env) -> None:
    s = suggestion(target_id="t2", focus="invalid")
    env.hil.receive(s)
    with pytest.raises(ValueError):
        env.hil.accept(s.id)
    assert env.hil.pending() == [s]


def test_reject_is_recorded(env: Env) -> None:
    s = suggestion()
    env.hil.receive(s)
    env.hil.reject(s.id)
    assert env.repo.resolved == {s.id: False}
    with pytest.raises(SuggestionNotFoundError):
        env.hil.reject(s.id)
