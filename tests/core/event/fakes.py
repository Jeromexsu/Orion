from core.contracts import Suggestion
from core.event import InstanceRecord, ParentEventRecord, TemplateDef


class InMemoryParentEventRepository:
    def __init__(self) -> None:
        self.items: dict[str, ParentEventRecord] = {}

    def get(self, parent_id: str) -> ParentEventRecord | None:
        return self.items.get(parent_id)

    def upsert(self, parent: ParentEventRecord) -> None:
        self.items[parent.id] = parent

    def list_all(self) -> list[ParentEventRecord]:
        return list(self.items.values())


class InMemoryTemplateRepository:
    def __init__(self) -> None:
        self.items: dict[tuple[str, int], TemplateDef] = {}

    def get(self, template_id: str, version: int | None = None) -> TemplateDef | None:
        if version is None:
            versions = self.list_versions(template_id)
            if not versions:
                return None
            version = versions[-1]
        return self.items.get((template_id, version))

    def upsert(self, template: TemplateDef) -> None:
        key = (template.id, template.version)
        if key in self.items and self.items[key] != template:
            raise ValueError(f"{key} already stored with different content")
        self.items[key] = template

    def list_versions(self, template_id: str) -> list[int]:
        return sorted(v for (tid, v) in self.items if tid == template_id)


class InMemoryInstanceRepository:
    def __init__(self) -> None:
        self.items: dict[str, InstanceRecord] = {}

    def find_active(self, parent_id: str, template_id: str) -> InstanceRecord | None:
        return next(
            (
                r
                for r in self.items.values()
                if r.parent_id == parent_id and r.template_id == template_id and r.closed_at is None
            ),
            None,
        )

    def save(self, instance: InstanceRecord) -> None:
        self.items[instance.id] = instance

    def history(self, parent_id: str, template_id: str) -> list[InstanceRecord]:
        return sorted(
            (r for r in self.items.values() if r.parent_id == parent_id and r.template_id == template_id),
            key=lambda r: r.opened_at,
        )


class RecordingSink:
    def __init__(self) -> None:
        self.received: list[Suggestion] = []

    def receive(self, suggestion: Suggestion) -> None:
        self.received.append(suggestion)
