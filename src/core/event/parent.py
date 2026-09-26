import logging
from datetime import UTC, datetime

from core.contracts import DRAFT, Draft, DynamicData
from core.event.definitions import TemplateDef
from core.event.errors import (
    TargetStillReferencedError,
    TemplateNotFoundError,
    TemplateVersionError,
)
from core.event.instance import SubEventInstance
from core.event.records import ParentEventRecord, TargetRef, TemplateRef
from core.event.runtime import EventRuntime
from core.event.slot import SubEventSlot
from core.event.template import SubEventTemplate
from core.target import ObservableTarget

logger = logging.getLogger(__name__)


class ParentEvent:
    """父事件：命名空间，持有目标池和一组子事件模板（每个模板一个 SubEventSlot）。

    它是 ObservableTarget 的引用者（Referencer）：加入目标池即 acquire，移出即 release。
    所有变更方法都会立即持久化自己的记录。通过 EventManager 创建和恢复。
    """

    def __init__(self, parent_id: str, name: str, runtime: EventRuntime) -> None:
        self._id = parent_id
        self._name = name
        self._runtime = runtime
        self._pool: dict[str, ObservableTarget] = {}
        self._slots: dict[str, SubEventSlot] = {}

    @classmethod
    def restore(cls, record: ParentEventRecord, runtime: EventRuntime) -> "ParentEvent":
        """重启恢复：重新 acquire 目标、重新编译模板、接回活跃实例。不写库。"""
        parent = cls(record.id, record.name, runtime)
        for ref in record.targets:
            parent._attach(runtime.targets.get_observable(ref.target_id, ref.focus))
        for ref in record.templates:
            definition = runtime.templates.get(ref.template_id, ref.version)
            if definition is None:
                raise TemplateNotFoundError(f"{ref.template_id} v{ref.version}")
            template = SubEventTemplate.compile(definition, runtime.conditions, runtime.operators)
            parent._slots[template.id] = SubEventSlot(
                parent.id,
                template,
                runtime,
                parent.target_names,
                active=parent._restore_active(template),
            )
        return parent

    # ------------------------------------------------------------ 只读

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    def targets(self) -> list[ObservableTarget]:
        return list(self._pool.values())

    def templates(self) -> list[SubEventTemplate]:
        return [s.template for s in self._slots.values()]

    def slot(self, template_id: str) -> SubEventSlot:
        try:
            return self._slots[template_id]
        except KeyError:
            raise TemplateNotFoundError(template_id) from None

    def target_names(self) -> dict[str, str]:
        """目标池里 ObservableTarget ID → 目标展示名，给算子上下文用。"""
        return {oid: obs.target.name for oid, obs in self._pool.items()}

    def to_record(self) -> ParentEventRecord:
        return ParentEventRecord(
            id=self._id,
            name=self._name,
            targets=[TargetRef(target_id=o.target.id, focus=o.focus) for o in self._pool.values()],
            templates=[
                TemplateRef(template_id=s.template.id, version=s.template.version)
                for s in self._slots.values()
            ],
        )

    # ------------------------------------------------------------ 目标池

    def add_target(self, target_id: str, focus: str) -> ObservableTarget:
        observable = self._runtime.targets.get_observable(target_id, focus)
        if observable.id not in self._pool:
            self._attach(observable)
            self._save()
        return observable

    def remove_target(self, observable_id: str) -> None:
        observable = self._pool.get(observable_id)
        if observable is None:
            return
        users = [s.template.id for s in self._slots.values() if observable_id in s.template.targets]
        if users:
            raise TargetStillReferencedError(f"{observable_id} is used by templates {users}")
        observable.release(self)
        del self._pool[observable_id]
        self._save()

    # ------------------------------------------------------------ 模板

    def upsert_template(self, definition: TemplateDef) -> SubEventTemplate:
        """编译 → 校验目标范围 → 保存新版本 → 装进槽（已有则替换，当前实例随之关闭）。"""
        template = SubEventTemplate.compile(
            definition, self._runtime.conditions, self._runtime.operators
        )
        template.validate(self._pool.keys())

        slot = self._slots.get(template.id)
        if slot is not None and template.version <= slot.template.version:
            raise TemplateVersionError(
                f"{template.id}: version {template.version} <= current {slot.template.version}"
            )

        self._runtime.templates.upsert(definition)
        if slot is None:
            self._slots[template.id] = SubEventSlot(
                self._id, template, self._runtime, self.target_names
            )
        else:
            slot.replace(template)
        self._save()
        return template

    def remove_template(self, template_id: str) -> None:
        slot = self._slots.pop(template_id, None)
        if slot is None:
            raise TemplateNotFoundError(template_id)
        slot.close_active("template_removed")
        self._save()

    # ------------------------------------------------------------ 报告

    def digest(self) -> Draft:
        """定时触发的汇总（原生方法，不是算子）：写进本父事件最近一份仍是“草稿”的报告，没有就新建。"""
        drafts = [d for d in self._runtime.reports.list_by_parent(self._id) if d.status == DRAFT]
        latest = max(drafts, key=lambda d: d.updated_at, default=None)
        return self._runtime.reports.write(
            self._id,
            title=f"{self._name} 汇总",
            content=self._digest_content(),
            draft_id=latest.id if latest else None,
        )

    def _digest_content(self) -> str:
        lines = [f"# {self._name}", "", "## 目标"]
        lines += [f"- {obs.target.name}（{obs.focus}）" for obs in self._pool.values()] or ["- 无"]
        lines += ["", "## 子事件"]
        for slot in self._slots.values():
            closed = sum(1 for r in slot.history() if r.closed_at is not None)
            active = slot.active
            state = f"进行中 {dict(active.status)}" if active else "无进行中实例"
            lines.append(f"- {slot.template.definition.name}：已收敛 {closed} 次，{state}")
        if not self._slots:
            lines.append("- 无")
        return "\n".join(lines)

    # ------------------------------------------------------------ Referencer

    def on_data(self, data: DynamicData) -> None:
        """Dispatcher 回调。每个槽单独隔离异常。"""
        if data.observable_id not in self._pool:
            return
        for slot in list(self._slots.values()):
            try:
                slot.on_data(data)
            except Exception:
                logger.exception(
                    "slot %s of parent %s failed on %s", slot.template.id, self._id, data.source_id
                )

    # ------------------------------------------------------------ 内部

    def _attach(self, observable: ObservableTarget) -> None:
        observable.acquire(self)
        self._pool[observable.id] = observable

    def _save(self) -> None:
        self._runtime.parents.upsert(self.to_record())

    def _restore_active(self, template: SubEventTemplate) -> SubEventInstance | None:
        record = self._runtime.instances.find_active(self._id, template.id)
        if record is None:
            return None
        if record.template_version != template.version:
            # 模板已换版本但旧实例没来得及关：补关
            self._runtime.instances.save(
                record.model_copy(
                    update={"closed_at": datetime.now(UTC), "close_reason": "template_replaced"}
                )
            )
            return None
        return SubEventInstance(record, template, self._runtime, self.target_names)
