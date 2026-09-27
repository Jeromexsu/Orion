import logging
from collections.abc import Callable

from core.event.definitions import TemplateDef
from core.event.errors import (
    TargetStillReferencedError,
    TemplateNotFoundError,
    TemplateScopeError,
)
from core.event.records import ParentEventRecord
from core.event.runner import EventRunner
from core.event.runtime import EventRuntime, ParentEventServices
from core.event.template import EventTemplate
from core.report import DRAFT, Draft
from core.target import TargetNotFoundError

logger = logging.getLogger(__name__)


class ParentEvent:
    """父事件：静态目标的命名空间 + 静态模板的集合。

    它自己不订阅任何东西——不知道观察点和上游。每个模板由一个 EventRunner 运行，
    runner 按模板的可观测目标声明订阅可观测目标、管理子事件生命周期。
    它不持久化自己：每次变更后调用 on_change，由 ParentEventManager 存档（与 runner 存子事件同理）。
    通过 ParentEventManager 创建和恢复。
    """

    def __init__(
        self,
        parent_id: str,
        name: str,
        services: ParentEventServices,
        runtime: EventRuntime,
        on_change: Callable[["ParentEvent"], None],
    ) -> None:
        self._id = parent_id
        self._name = name
        self._services = services   # 父事件自己的依赖
        self._runtime = runtime     # 转交给 runner 的依赖
        self._on_change = on_change  # 变更后通知 manager 存档
        self._targets: set[str] = set()
        self._runners: dict[str, EventRunner] = {}

    @classmethod
    def restore(
        cls,
        record: ParentEventRecord,
        services: ParentEventServices,
        runtime: EventRuntime,
        on_change: Callable[["ParentEvent"], None],
    ) -> "ParentEvent":
        """重启恢复：还原命名空间；读回模板定义并编译（当前版本和挂起版本），交给 runner 恢复。不触发 on_change。"""
        parent = cls(record.id, record.name, services, runtime, on_change)
        parent._targets = set(record.targets)
        for ref in record.templates:
            template = parent._load_template(ref.template_id, ref.version)
            pending = (
                parent._load_template(ref.template_id, ref.pending_version)
                if ref.pending_version is not None
                else None
            )
            parent._runners[ref.template_id] = EventRunner.restore(
                parent.id, template, pending, runtime, parent._changed
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
        """目标命名空间。"""
        return frozenset(self._targets)

    def templates(self) -> list[EventTemplate]:
        """各模板当前运行的版本（不含挂起版本）。"""
        return [s.template for s in self._runners.values()]

    def runner(self, template_id: str) -> EventRunner:
        """某个模板的 runner。不存在抛 TemplateNotFoundError。"""
        try:
            return self._runners[template_id]
        except KeyError:
            raise TemplateNotFoundError(template_id) from None

    def to_record(self) -> ParentEventRecord:
        """当前状态的持久化记录。"""
        return ParentEventRecord(
            id=self._id,
            name=self._name,
            targets=sorted(self._targets),
            templates=[s.to_ref() for s in self._runners.values()],
        )

    # ------------------------------------------------------------ 目标命名空间

    def add_target(self, target_id: str) -> None:
        """把静态目标加入命名空间（触发 on_change）。目标不存在抛 TargetNotFoundError；已在命名空间里忽略。"""
        self._services.target_manager.get_target(target_id)
        if target_id not in self._targets:
            self._targets.add(target_id)
            self._changed()

    def remove_target(self, target_id: str) -> None:
        """从命名空间移除（触发 on_change）。仍被某个模板（含挂起版本）观测抛 TargetStillReferencedError；不在其中忽略。"""
        if target_id not in self._targets:
            return
        users = [tid for tid, s in self._runners.items() if target_id in s.target_ids()]
        if users:
            raise TargetStillReferencedError(f"{target_id} is observed by templates {users}")
        self._targets.discard(target_id)
        self._changed()

    # ------------------------------------------------------------ 模板

    def upsert_template(self, template_def: TemplateDef) -> EventTemplate:
        """检查命名空间与版本（只看定义）→ 编译 → 保存定义 → 启动 runner 或交给已有 runner。返回编译好的模板。

        只看定义就能做的检查放在编译之前：不白做编译，也不会为越界的模板创建可观测目标。
        新版本交给已有 runner 时按「下个周期生效」挂起或立即切换。
        越界抛 TemplateScopeError；版本不大于现有版本抛 TemplateVersionError；编译失败抛 TemplateCompileError。
        任一检查失败时什么都不写。
        """

        # check if targets defined in template are in the target namespace
        self._check_namespace(template_def)

        # check if there is a runner for this template
        runner = self._runners.get(template_def.id)

        # if there is an existing runner, check version (must > current and pending version)
        if runner is not None:
            runner.check_version(template_def.version)

        # compile template
        template = self._services.template_compiler.compile(template_def)

        # compile pass, syntax ok, save template definition
        self._services.template_repository.upsert(template_def)

        # kick off new runner if there is no runner for the compiled template
        if runner is None:
            self._runners[template.id] = EventRunner.start(
                self._id, template, self._runtime, self._changed
            )
            self._changed()
        else:
            runner.stage(template)   # 内部通过 on_change 存档
        return template

    def remove_template(self, template_id: str) -> None:
        """移除模板：runner 关闭活跃子事件、取消订阅、删除开启条件状态，然后触发 on_change。

        不存在抛 TemplateNotFoundError。模板定义的历史版本保留在模板仓库里。
        """
        runner = self._runners.pop(template_id, None)
        if runner is None:
            raise TemplateNotFoundError(template_id)
        runner.dispose("template_removed")
        self._changed()

    # ------------------------------------------------------------ 报告

    def digest(self) -> Draft:
        """定时触发的汇总（原生方法，不是钩子）：写进本父事件最近一份仍是“草稿”的报告，没有就新建。"""
        reports = self._services.report_manager
        drafts = [d for d in reports.list_by_parent(self._id) if d.status == DRAFT]
        latest = max(drafts, key=lambda d: d.updated_at, default=None)
        return reports.write(
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
                f"- {runner.template.template_def.name} v{runner.template.version}{pending}："
                f"已结束 {closed} 个周期，{state}"
            )
        if not self._runners:
            lines.append("- 无")
        return "\n".join(lines)

    # ------------------------------------------------------------ 内部

    def _target_name(self, target_id: str) -> str:
        try:
            return self._services.target_manager.get_target(target_id).name
        except TargetNotFoundError:
            return target_id

    def _check_namespace(self, template_def: TemplateDef) -> None:
        """观测的目标必须都在目标命名空间里。"""
        missing = template_def.target_ids - self._targets
        if missing:
            raise TemplateScopeError(
                f"template {template_def.id} v{template_def.version} observes targets outside "
                f"the namespace: {sorted(missing)}"
            )

    def _load_template(self, template_id: str, version: int) -> EventTemplate:
        template_def = self._services.template_repository.get(template_id, version)
        if template_def is None:
            raise TemplateNotFoundError(f"{template_id} v{version}")
        return self._services.template_compiler.compile(template_def)

    def _changed(self) -> None:
        self._on_change(self)
