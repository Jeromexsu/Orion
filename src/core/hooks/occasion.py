"""Occasions: why a hook is being run — at which mount point, and what happened there.

One type per mount point, so a hook can match on it and get fields that are always
set (no Optional). Pydantic so an occasion can later travel with an async output hook
through a queue.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from core.condition_engine import EvalResult
from core.target import ObservationEnvelope


class CreatedOccasion(BaseModel):
    """The event was just opened."""

    model_config = ConfigDict(frozen=True)

    mount_point: Literal["created"] = "created"


class ObservationOccasion(BaseModel):
    """An observation arrived: before the rules are evaluated (pre) or after (post)."""

    model_config = ConfigDict(frozen=True)

    mount_point: Literal["pre", "post"]
    envelope: ObservationEnvelope


class RuleHitOccasion(BaseModel):
    """A rule's condition hit on an observation."""

    model_config = ConfigDict(frozen=True)

    mount_point: Literal["rule_hit"] = "rule_hit"
    envelope: ObservationEnvelope
    result: EvalResult          # the hit rule's evaluation result


class ClosedOccasion(BaseModel):
    """The event is being closed."""

    model_config = ConfigDict(frozen=True)

    mount_point: Literal["closed"] = "closed"
    reason: str                 # why it closes, e.g. "converged"


Occasion = Annotated[
    CreatedOccasion
    | ObservationOccasion
    | RuleHitOccasion
    | ClosedOccasion,
    Field(discriminator="mount_point"),
]
"""Why a hook is being run; tell the kinds apart with match / isinstance."""
