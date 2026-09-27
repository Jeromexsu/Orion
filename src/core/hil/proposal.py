"""A proposal is a change to be reviewed, not a finding."""

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class ProposalOrigin(BaseModel):
    """Where a proposal came from. Filled in by the hook context, not by the hook."""

    model_config = ConfigDict(frozen=True)

    hook: str                   # hook name
    mount: str                  # mount name in the template
    parent_id: str
    event_id: str


class Proposal(BaseModel):
    """A proposed change: where it came from, why, and the whitelisted action to run with
    which arguments if an analyst accepts it."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: uuid4().hex)
    origin: ProposalOrigin
    action: str                 # a whitelisted action, e.g. "add_target"
    # the action's arguments as JSON; checked against its args model when received
    args: dict[str, Any] = Field(default_factory=dict[str, Any])
    reason: str                 # human-readable reason
    # source_ids of the observations it relies on
    evidence: list[str] = Field(default_factory=list[str])
