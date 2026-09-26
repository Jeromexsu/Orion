from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from core.target import Target, TargetManager
from tests.core.target.conftest import Subscriber


def test_acquire_is_idempotent_and_release_tolerant(manager: TargetManager, plane: Target) -> None:
    obs = manager.get_observable(plane.id, "position")
    sub = Subscriber()
    obs.acquire(sub)
    obs.acquire(sub)
    assert obs.referencers() == frozenset({sub})
    obs.release(sub)
    obs.release(sub)
    assert not obs.is_active


def test_referencers_is_a_snapshot(manager: TargetManager, plane: Target) -> None:
    obs = manager.get_observable(plane.id, "position")
    a, b = Subscriber(), Subscriber()
    obs.acquire(a)
    obs.acquire(b)
    snapshot = obs.referencers()
    obs.release(a)
    assert snapshot == frozenset({a, b})


def test_query_spec(manager: TargetManager, plane: Target) -> None:
    since = datetime(2026, 9, 1, tzinfo=UTC)
    spec = manager.get_observable(plane.id, "position").query_spec(since)
    assert spec.type == "aircraft"
    assert spec.focus == "position"
    assert spec.attributes["registration"] == "B-2447"
    assert spec.aliases == ["MU5101"]
    assert spec.since == since


def test_validate_fields(manager: TargetManager, plane: Target) -> None:
    obs = manager.get_observable(plane.id, "position")
    assert obs.validate_fields({"lat": "31.2", "lon": 121.3}) == {
        "lat": 31.2,
        "lon": 121.3,
        "altitude_m": None,
    }
    with pytest.raises(ValidationError):
        obs.validate_fields({"lat": 31.2})


def test_rebind_target_rejects_other_id(manager: TargetManager, plane: Target) -> None:
    obs = manager.get_observable(plane.id, "position")
    with pytest.raises(ValueError):
        obs.rebind_target(plane.model_copy(update={"id": "t2"}))
