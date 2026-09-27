from typing import Any

from core.event import EventRecord, ParentEventRecord, TemplateDef
from core.hil import Proposal


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


class InMemoryEventRepository:
    def __init__(self) -> None:
        self.items: dict[str, EventRecord] = {}

    def find_active(self, parent_id: str, template_id: str) -> EventRecord | None:
        return next(
            (
                r
                for r in self.items.values()
                if r.parent_id == parent_id and r.template_id == template_id and r.closed_at is None
            ),
            None,
        )

    def save(self, record: EventRecord) -> None:
        self.items[record.id] = record

    def count_closed(self, parent_id: str, template_id: str) -> int:
        return sum(1 for r in self.records(parent_id, template_id) if r.closed_at is not None)

    def records(self, parent_id: str, template_id: str) -> list[EventRecord]:
        """测试用：某模板下的全部记录，按开启时间排序。"""
        return sorted(
            (r for r in self.items.values() if r.parent_id == parent_id and r.template_id == template_id),
            key=lambda r: r.opened_at,
        )


class RecordingSink:
    def __init__(self) -> None:
        self.received: list[Proposal] = []

    def receive(self, proposal: Proposal) -> None:
        self.received.append(proposal)


class InMemoryRunnerStateRepository:
    def __init__(self) -> None:
        self.items: dict[tuple[str, str], dict[str, Any]] = {}

    def get(self, parent_id: str, template_id: str) -> dict[str, Any] | None:
        state = self.items.get((parent_id, template_id))
        return dict(state) if state is not None else None

    def save(self, parent_id: str, template_id: str, state: dict[str, Any]) -> None:
        self.items[(parent_id, template_id)] = dict(state)

    def remove(self, parent_id: str, template_id: str) -> None:
        self.items.pop((parent_id, template_id), None)
