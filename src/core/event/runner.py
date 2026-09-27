import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from core.condition_engine import HIT, apply_state_patch
from core.event.errors import TemplateVersionError
from core.event.event import Event
from core.event.records import EventRecord, TemplateRef
from core.event.runtime import EventRuntime
from core.event.template import EventTemplate
from core.target import ObservableTarget, ObservationEnvelope

logger = logging.getLogger(__name__)


class EventRunner:
    """运行中的模板：管理这个模板的子事件生命周期。

    - 订阅：按模板的可观测目标声明 acquire 可观测目标，自己就是订阅者（Dispatcher 直接回调）；
    - 开启：每条数据都评估开启条件并更新其状态；无活跃子事件且命中时开新子事件，并把该条数据交给它；
    - 运行：有活跃子事件时数据交给子事件处理（同一模板最多一个活跃子事件）；
    - 换版本：新版本只对下一个周期生效——有活跃子事件时挂起，子事件关闭后切换并重新订阅；
    - 存档：子事件记录每处理一条数据就存；开启条件状态单独持久化（年度事件跨越多次重启）。
    """

    def __init__(
        self,
        parent_id: str,
        template: EventTemplate,
        runtime: EventRuntime,
        on_change: Callable[[], None],
        *,
        pending: EventTemplate | None = None,
        open_state: dict[str, Any] | None = None,
        active: Event | None = None,
    ) -> None:
        self._parent_id = parent_id
        self._template = template
        self._runtime = runtime
        self._on_change = on_change        # 模板版本变化时通知父事件存档
        self._pending = pending
        self._open_state: dict[str, Any] = open_state or {}
        self._active = active
        self._observables: dict[str, ObservableTarget] = {}

    @classmethod
    def start(
        cls,
        parent_id: str,
        template: EventTemplate,
        runtime: EventRuntime,
        on_change: Callable[[], None],
    ) -> "EventRunner":
        """新装入模板：订阅并开始评估开启条件。模板须已编译通过（可观测目标声明已校验）。"""
        runner = cls(parent_id, template, runtime, on_change)
        runner._subscribe()
        return runner

    @classmethod
    def restore(
        cls,
        parent_id: str,
        template: EventTemplate,
        pending: EventTemplate | None,
        runtime: EventRuntime,
        on_change: Callable[[], None],
    ) -> "EventRunner":
        """重启恢复：读回开启条件状态、接回活跃子事件、重新订阅。模板由父事件编译好传入。不写库。"""
        runner = cls(
            parent_id,
            template,
            runtime,
            on_change,
            pending=pending,
            open_state=runtime.runner_state_repository.get(parent_id, template.id),
        )
        runner._active = runner._restore_active()
        runner._subscribe()
        return runner

    # ------------------------------------------------------------ 只读

    @property
    def template(self) -> EventTemplate:
        return self._template

    @property
    def pending(self) -> EventTemplate | None:
        return self._pending

    @property
    def active(self) -> Event | None:
        return self._active

    @property
    def open_state(self) -> dict[str, Any]:
        return dict(self._open_state)

    def target_ids(self) -> frozenset[str]:
        """当前与挂起版本观测的静态目标，父事件移除目标时据此检查。"""
        ids = self._template.target_ids
        return ids | self._pending.target_ids if self._pending else ids

    def target_names(self) -> dict[str, str]:
        """订阅中的可观测目标 ID → 目标展示名，给算子上下文用。"""
        return {oid: obs.target.name for oid, obs in self._observables.items()}

    def history(self) -> list[EventRecord]:
        return self._runtime.event_repository.history(self._parent_id, self._template.id)

    def to_ref(self) -> TemplateRef:
        return TemplateRef(
            template_id=self._template.id,
            version=self._template.version,
            pending_version=self._pending.version if self._pending else None,
        )

    # ------------------------------------------------------------ Referencer

    def on_observation(self, envelope: ObservationEnvelope) -> None:
        if envelope.observable_id not in self._observables:
            return

        opened = self._template.open_tree.evaluate(envelope, self._open_state)
        if opened.state_patch:
            self._open_state = apply_state_patch(self._open_state, opened.state_patch)
            self._runtime.runner_state_repository.save(self._parent_id, self._template.id, self._open_state)

        if self._active is None:
            if opened.outcome != HIT:
                return
            self._active = Event.open(
                self._parent_id,
                self._template,
                self._runtime,
                self.target_names,
                cycle=envelope.occurred_at.year,
            )

        event = self._active
        event.process(envelope)
        self._runtime.event_repository.save(event.to_record())
        if event.is_closed:
            self._end_cycle()

    # ------------------------------------------------------------ 版本 / 生命周期

    def check_version(self, version: int) -> None:
        """新版本号必须大于当前版本和挂起版本。"""
        latest = self._pending.version if self._pending else self._template.version
        if version <= latest:
            raise TemplateVersionError(
                f"{self._template.id}: version {version} <= latest {latest}"
            )

    def stage(self, template: EventTemplate) -> None:
        """发布新版本：无活跃子事件立即切换，否则挂起到当前子事件关闭。调用前应已 check_version。"""
        if self._active is None:
            self._switch(template)
        else:
            self._pending = template
            self._on_change()

    def close_active(self, reason: str) -> None:
        """手动关闭当前子事件（如分析师判定本周期结束），之后按挂起版本切换。"""
        if self._active is None:
            return
        self._active.close(reason)
        self._runtime.event_repository.save(self._active.to_record())
        self._end_cycle()

    def dispose(self, reason: str) -> None:
        """模板被移除：关闭当前子事件、取消全部订阅、删除开启条件状态。"""
        if self._active is not None:
            self._active.close(reason)
            self._runtime.event_repository.save(self._active.to_record())
            self._active = None
        for observable in self._observables.values():
            observable.release(self)
        self._observables = {}
        self._runtime.runner_state_repository.remove(self._parent_id, self._template.id)

    # ------------------------------------------------------------ 内部

    def _end_cycle(self) -> None:
        self._active = None
        if self._pending is not None:
            self._switch(self._pending)

    def _switch(self, template: EventTemplate) -> None:
        """切换到新版本：开启条件树可能不同，状态清空；按新可观测目标声明重新订阅。"""
        self._template = template
        self._pending = None
        self._open_state = {}
        self._runtime.runner_state_repository.save(self._parent_id, template.id, self._open_state)
        self._subscribe()
        self._on_change()

    def _subscribe(self) -> None:
        """按模板里解析好的可观测目标订阅；新版本不再需要的可观测目标 release。"""
        subscribed: dict[str, ObservableTarget] = {}
        for c in self._template.compiled_observables:
            c.observable.acquire(self, c.upstreams)
            subscribed[c.observable.id] = c.observable
        for oid, observable in self._observables.items():
            if oid not in subscribed:
                observable.release(self)
        self._observables = subscribed

    def _restore_active(self) -> Event | None:
        record = self._runtime.event_repository.find_active(self._parent_id, self._template.id)
        if record is None:
            return None
        if record.template_version != self._template.version:
            # 不应出现（子事件总按当前版本运行）；防御性补关，避免孤儿活跃记录
            logger.error("active event %s has stale version; closing", record.id)
            self._runtime.event_repository.save(
                record.model_copy(
                    update={"closed_at": datetime.now(UTC), "close_reason": "version_mismatch"}
                )
            )
            return None
        return Event(record, self._template, self._runtime, self.target_names)

