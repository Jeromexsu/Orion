from collections.abc import Callable, Mapping
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from core.hil.errors import (
    ActionNotAllowedError,
    DuplicateActionError,
    InvalidProposalArgsError,
    ProposalNotFoundError,
)
from core.hil.proposal import Proposal
from core.hil.repository import ProposalRepository

A = TypeVar("A", bound=BaseModel)


class _Action:
    """A whitelisted action: its argument model and the core public method it calls."""

    def __init__(self, args_model: type[BaseModel], handler: Callable[[Any], object]) -> None:
        self.args_model = args_model
        self.handler = handler

    def parse(self, args: Mapping[str, Any]) -> BaseModel:
        try:
            return self.args_model.model_validate(dict(args))
        except ValidationError as e:
            raise InvalidProposalArgsError(str(e)) from None


class HilManager:
    """Human in the loop: proposals wait for an analyst before anything changes.

    Implements the hooks' ProposalSink structurally. accept() can only call whitelisted
    core public methods, which do their own full validation, so a proposal cannot get
    around them. bootstrap registers the whitelist with allow(); a new proposing hook
    needs no change here.
    """

    def __init__(self, proposal_repository: ProposalRepository) -> None:
        self._proposal_repository = proposal_repository
        self._actions: dict[str, _Action] = {}

    # ------------------------------------------------------------ whitelist

    def allow(self, action: str, args_model: type[A], handler: Callable[[A], object]) -> None:
        """Whitelist a core public method under an action name.

        Args:
            args_model: The shape of the action's arguments. Proposals are checked
                against it when received, and again after the analyst's overrides.

        Raises:
            DuplicateActionError: If the action name is taken.
        """
        if action in self._actions:
            raise DuplicateActionError(action)
        self._actions[action] = _Action(args_model, handler)

    def allowed_actions(self) -> list[str]:
        """Whitelisted action names, sorted."""
        return sorted(self._actions)

    # ------------------------------------------------------------ ProposalSink

    def receive(self, proposal: Proposal) -> None:
        """Store a proposal for review.

        Raises:
            ActionNotAllowedError: If the action is not whitelisted.
            InvalidProposalArgsError: If the arguments do not fit the action's model.
                Either way the proposal never reaches the review queue.
        """
        self._action(proposal).parse(proposal.args)
        self._proposal_repository.save(proposal)

    # ------------------------------------------------------------ review

    def pending(self) -> list[Proposal]:
        """All proposals waiting for review."""
        return self._proposal_repository.get_pending()

    def accept(self, proposal_id: str, overrides: Mapping[str, Any] | None = None) -> object:
        """Accept a proposal and run its action; marks it accepted once the action succeeds.

        Args:
            overrides: Arguments the analyst changed before accepting; they replace the
                proposed ones of the same name.

        Returns:
            What the whitelisted method returned.

        Raises:
            ProposalNotFoundError: If it does not exist or was already resolved.
            InvalidProposalArgsError: If the arguments with overrides do not fit the
                action's model. The proposal stays pending.
            Exception: Whatever the core public method raises when its own validation
                fails, unchanged. The proposal stays pending.
        """
        proposal = self._pending(proposal_id)
        action = self._action(proposal)
        args = action.parse({**proposal.args, **(overrides or {})})
        result = action.handler(args)
        self._proposal_repository.mark_resolved(proposal_id, accepted=True)
        return result

    def reject(self, proposal_id: str) -> None:
        """Reject a proposal and keep the record (for per-hook acceptance rates later).

        Raises:
            ProposalNotFoundError: If it does not exist or was already resolved.
        """
        self._pending(proposal_id)
        self._proposal_repository.mark_resolved(proposal_id, accepted=False)

    def _action(self, proposal: Proposal) -> _Action:
        action = self._actions.get(proposal.action)
        if action is None:
            raise ActionNotAllowedError(f"{proposal.origin.hook} proposed {proposal.action!r}")
        return action

    def _pending(self, proposal_id: str) -> Proposal:
        proposal = self._proposal_repository.get_pending_by_id(proposal_id)
        if proposal is None:
            raise ProposalNotFoundError(proposal_id)
        return proposal
