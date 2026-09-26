from core.contracts import Draft


class InMemoryDraftRepository:
    def __init__(self) -> None:
        self.items: dict[str, Draft] = {}

    def get(self, draft_id: str) -> Draft | None:
        return self.items.get(draft_id)

    def upsert(self, draft: Draft) -> None:
        self.items[draft.id] = draft

    def list_by_parent(self, parent_id: str) -> list[Draft]:
        return [d for d in self.items.values() if d.parent_id == parent_id]
