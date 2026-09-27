"""What a hook may see and do while it runs, built per run from its declaration."""

from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any

from core.hil import Proposal
from core.hooks.errors import UndeclaredCapabilityError


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

    Always available: a copy of this mount's own state (return the new state from run
    to change it; no scope needed), target display names and where it runs, read-only.
    Capabilities exist only if declared: ctx.event needs scopes={"event"}, ctx.propose
    needs proposes=True; using an undeclared one raises UndeclaredCapabilityError.
    The external scope has no capability here: output channels (reports, notifications)
    are injected into the hook when it is constructed.
    """

    def __init__(
        self,
        *,
        state: Mapping[str, Any],
        target_names: Mapping[str, str],
        parent_id: str,
        event_id: str,
        event: EventHandle | None = None,
        propose: Callable[[Proposal], None] | None = None,
    ) -> None:
        # this mount's state, a copy: return the new state from run to keep it
        self.state = deepcopy(dict(state))
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

    def propose(self, proposal: Proposal) -> None:
        """Send a proposal for review; nothing changes until an analyst accepts it.

        What it would change (the parent event, a target, ...) is decided by the
        proposed action. Requires proposes=True.
        """
        if self._propose is None:
            raise UndeclaredCapabilityError("declare proposes=True to make proposals")
        self._propose(proposal)
