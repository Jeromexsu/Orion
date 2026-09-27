"""A proposal is a change to be reviewed, not a finding."""

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class Proposal(BaseModel):
    """A proposed change: who proposed it and why, and the whitelisted action to run
    if an analyst accepts it."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: uuid4().hex)
    source: str                 # name of the hook that proposed it
    reason: str                 # human-readable reason
    # source_ids of the observations it relies on
    evidence: list[str] = Field(default_factory=list[str])
    action: str                 # a whitelisted core public method, e.g. "add_target"
    target: str | None = None   # ID of what the action acts on
    args: dict[str, Any] = Field(default_factory=dict[str, Any])
