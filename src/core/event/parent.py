import logging

from core.event.definitions import TemplateDef
from core.event.errors import TargetStillReferencedError, TemplateNotFoundError
from core.event.records import ParentEventRecord
from core.event.runner import EventRunner, check_observation_defs
from core.event.runtime import EventRuntime
from core.event.template import EventTemplate
from core.report import DRAFT, Draft
from core.target import TargetNotFoundError

logger = logging.getLogger(__name__)


class ParentEvent:
    """父事件：静态目标的命名空间 + 静态模板的集合。

    它自己不订阅任何东西——不知道关注点和上游。每个模板由一个 EventRunner 运行，
    runner 按模板的观测声明订阅可观测目标、管理子事件生命周期。
    所有变更方法都会立即持久化自己的记录。通过 ParentEventManager 创建和恢复。
    """

    def __init__(self, parent_id: str, name: str, runtime: EventRuntime) -> None:
        self._id = parent_id
        self._name = name
        self._runtime = runtime
        self._targets: set[str] = set()
        self._runners: dict[str, EventRunner] = {}

    @classmethod
    def restore(cls, record: ParentEventRecord, runtime: EventRuntime) -> "ParentEvent":
        """重启恢复：还原命名空间，各 runner 重新订阅并接回活跃子事件。不写库。"""
        parent = cls(record.id, record.name, runtime)
        parent._targets = set(record.targets)
        for ref in record.templates:
            parent._runners[ref.template_id] = EventRunner.restore(
                parent.id, ref, runtime, parent._save
            )
        return parent

    # ------------------------------------------------------------ 只读

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    def target_ids(self) -> frozenset[str]:
        return frozenset(self._targets)

    def templates(self) -> list[EventTemplate]:
        return [s.template for s in self._runners.values()]

    def runner(self, template_id: str) -> EventRunner:
        try:
            return self._runners[template_id]
        except KeyError:
            raise TemplateNotFoundError(template_id) from None

    def to_record(self) -> ParentEventRecord:
        return ParentEventRecord(
            id=self._id,
            name=self._name,
            targets=sorted(self._targets),
            templates=[s.to_ref() for s in self._runners.values()],
        )

    # ------------------------------------------------------------ 目标命名空间

    def add_target(self, target_id: str) -> None:
        """把静态目标加入命名空间。目标必须已存在。"""
        self._runtime.targets.get_target(target_id)
        if target_id not in self._targets:
            self._targets.add(target_id)
            self._save()

    def remove_target(self, target_id: str) -> None:
        if target_id not in self._targets:
            return
        users = [tid for tid, s in self._runners.items() if target_id in s.target_ids()]
        if users:
            raise TargetStillReferencedError(f"{target_id} is observed by templates {users}")
        self._targets.discard(target_id)
        self._save()

    # ------------------------------------------------------------ 模板

    def upsert_template(self, definition: TemplateDef) -> EventTemplate:
        """编译 → 校验命名空间与观测声明 → 保存新版本 → 装入（已有则按「下个周期生效」挂起或切换）。"""
        template = EventTemplate.compile(
            definition, self._runtime.conditions, self._runtime.operators
        )
        template.validate(self._targets)
        check_observation_defs(template, self._runtime.targets)

        runner = self._runners.get(template.id)
        if runner is not None:
            runner.check_version(template)

        self._runtime.templates.upsert(definition)
        if runner is None:
            self._runners[template.id] = EventRunner.start(
                self._id, template, self._runtime, self._save
            )
            self._save()
        else:
            runner.stage(template)   # 内部通过 on_change 存档
        return template

    def remove_template(self, template_id: str) -> None:
        runner = self._runners.pop(template_id, None)
        if runner is None:
            raise TemplateNotFoundError(template_id)
        runner.dispose("template_removed")
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
        lines += [f"- {self._target_name(t)}" for t in sorted(self._targets)] or ["- 无"]
        lines += ["", "## 子事件"]
        for runner in self._runners.values():
            closed = sum(1 for r in runner.history() if r.closed_at is not None)
            active = runner.active
            state = (
                f"{active.cycle} 周期进行中 {dict(active.status)}" if active else "未开启"
            )
            pending = f"（v{runner.pending.version} 待下个周期生效）" if runner.pending else ""
            lines.append(
                f"- {runner.template.definition.name} v{runner.template.version}{pending}："
                f"已结束 {closed} 个周期，{state}"
            )
        if not self._runners:
            lines.append("- 无")
        return "\n".join(lines)

    # ------------------------------------------------------------ 内部

    def _target_name(self, target_id: str) -> str:
        try:
            return self._runtime.targets.get_target(target_id).name
        except TargetNotFoundError:
            return target_id

    def _save(self) -> None:
        self._runtime.parents.upsert(self.to_record())
