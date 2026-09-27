from core.hil import Proposal


class InMemoryProposalRepository:
    def __init__(self) -> None:
        self.items: dict[str, Proposal] = {}
        self.resolved: dict[str, bool] = {}

    def save(self, proposal: Proposal) -> None:
        self.items[proposal.id] = proposal

    def get_pending_by_id(self, proposal_id: str) -> Proposal | None:
        if proposal_id in self.resolved:
            return None
        return self.items.get(proposal_id)

    def get_pending(self) -> list[Proposal]:
        return [s for s in self.items.values() if s.id not in self.resolved]

    def mark_resolved(self, proposal_id: str, accepted: bool) -> None:
        self.resolved[proposal_id] = accepted
