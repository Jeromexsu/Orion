from core.hil import Suggestion


class InMemorySuggestionRepository:
    def __init__(self) -> None:
        self.items: dict[str, Suggestion] = {}
        self.resolved: dict[str, bool] = {}

    def save(self, suggestion: Suggestion) -> None:
        self.items[suggestion.id] = suggestion

    def get_pending_by_id(self, suggestion_id: str) -> Suggestion | None:
        if suggestion_id in self.resolved:
            return None
        return self.items.get(suggestion_id)

    def get_pending(self) -> list[Suggestion]:
        return [s for s in self.items.values() if s.id not in self.resolved]

    def mark_resolved(self, suggestion_id: str, accepted: bool) -> None:
        self.resolved[suggestion_id] = accepted
