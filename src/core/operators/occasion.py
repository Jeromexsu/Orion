"""Occasions: why an operator is being run — at which mount point, and what happened there.

One type per mount point, so an operator can match on it and get fields that are always
set (no Optional). Pydantic so an occasion can later travel with an async output operator
through a queue.
"""

from typing import Annotated, Any, Literal

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


class StatusUpdatedOccasion(BaseModel):
    """The event's status was updated by a progress operator."""

    model_config = ConfigDict(frozen=True)

    mount_point: Literal["status_updated"] = "status_updated"
    patch: dict[str, Any]       # what was merged into the status


class ClosedOccasion(BaseModel):
    """The event is being closed."""

    model_config = ConfigDict(frozen=True)

    mount_point: Literal["closed"] = "closed"


Occasion = Annotated[
    CreatedOccasion
    | ObservationOccasion
    | RuleHitOccasion
    | StatusUpdatedOccasion
    | ClosedOccasion,
    Field(discriminator="mount_point"),
]
"""Why an operator is being run; tell the kinds apart with match / isinstance."""
