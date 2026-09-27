"""What a hook gets when it runs: why (Occasion), what it may see and do (HookContext),
and where its proposals go (ProposalSink).

Occasions have one type per mount point, so a hook can match on it and get fields that
are always set (no Optional); Pydantic so an occasion can later travel with an async
output hook through a queue. The context is built per run from the hook's declaration.
"""

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from typing import Annotated, Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from core.condition_engine import EvalResult
from core.hil import Proposal, ProposalOrigin
from core.hooks.errors import UndeclaredCapabilityError
from core.observation import ObservationEnvelope

# ------------------------------------------------------------ 调用时机：为什么被调用


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


# ------------------------------------------------------------ 提议的去处


class ProposalSink(Protocol):
    """提议的去处。由 hil 实现，bootstrap 时注入 event。"""

    def receive(self, proposal: Proposal) -> None:
        """接收一条提议（hil 存为待处理）。"""
        ...


# ------------------------------------------------------------ 上下文：能看到什么、能做什么


class EventHandle:
    """What a hook with the event scope may do to the event it runs on.

    Only closing for now. A hook's own state is not part of this: every mount keeps
    its own and changes it by returning it from run.
    """

    def __init__(self, request_close: Callable[[str], None]) -> None:
        self._request_close = request_close

    def close(self, reason: str) -> None:
        """Ask for the event to close.

        The event closes once the current observation has been processed (its
        remaining rules and post hooks still run), not in the middle of it.
        """
        self._request_close(reason)


class HookContext:
    """What a hook gets about the event it runs on, besides the occasion and its parameters.

    Always available: which hook and mount it is, a copy of this mount's own state
    (return the new state from run to change it; no scope needed), target display names
    and where it runs, read-only.
    Capabilities exist only if declared: ctx.event needs scopes={"event"}, ctx.propose
    needs proposes=True; using an undeclared one raises UndeclaredCapabilityError.
    The external scope has no capability here: output channels (reports, notifications)
    are injected into the hook when it is constructed.
    """

    def __init__(
        self,
        *,
        hook_name: str,
        mount_name: str,
        state: Mapping[str, Any],
        target_names: Mapping[str, str],
        parent_id: str,
        event_id: str,
        event: EventHandle | None = None,
        propose: Callable[[Proposal], None] | None = None,
    ) -> None:
        # this mount's state, a copy: return the new state from run to keep it
        self.state = deepcopy(dict(state))
        self.hook_name = hook_name
        self.mount_name = mount_name
        self.parent_id = parent_id
        self.event_id = event_id
        self._target_names = dict(target_names)
        self._event = event
        self._propose = propose

    def target_name(self, observable_id: str) -> str:
        """Display name of the target behind an observable target; the ID if unknown."""
        return self._target_names.get(observable_id, observable_id)

    @property
    def target_names(self) -> dict[str, str]:
        """Observable target ID -> display name of its target, for the observable targets
        the event subscribes to."""
        return dict(self._target_names)

    @property
    def event(self) -> EventHandle:
        """Change the event directly. Requires scopes={"event"}."""
        if self._event is None:
            raise UndeclaredCapabilityError("declare scopes={'event'} to change the event")
        return self._event

    def propose(
        self,
        action: str,
        args: Mapping[str, Any],
        *,
        reason: str,
        evidence: Sequence[str] = (),
    ) -> None:
        """Send a proposal for review; nothing changes until an analyst accepts it.

        Where it came from (hook, mount, parent event, event) is filled in here, not by
        the hook.
        What it would change (the parent event, a target, ...) is decided by the action.
        Requires proposes=True.

        Args:
            action: A whitelisted action name, e.g. "add_target".
            args: The action's arguments, checked against its args model right away.
            reason: Why, for the analyst.
            evidence: source_ids of the observations it relies on.

        Raises:
            ActionNotAllowedError: If the action is not whitelisted (from hil).
            InvalidProposalArgsError: If args do not fit the action (from hil).
        """
        if self._propose is None:
            raise UndeclaredCapabilityError("declare proposes=True to make proposals")
        origin = ProposalOrigin(
            hook=self.hook_name,
            mount=self.mount_name,
            parent_id=self.parent_id,
            event_id=self.event_id,
        )
        self._propose(
            Proposal(
                origin=origin,
                action=action,
                args=dict(args),
                reason=reason,
                evidence=list(evidence),
            )
        )
