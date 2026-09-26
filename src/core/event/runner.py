import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from core.condition_engine import HIT, apply_state_patch
from core.event.errors import TemplateNotFoundError, TemplateVersionError
from core.event.event import Event
from core.event.records import EventRecord, TemplateRef
from core.event.runtime import EventRuntime
from core.event.template import EventTemplate
from core.target import ObservableTarget, Observation

logger = logging.getLogger(__name__)


class EventRunner:
    """运行中的模板：管理这个模板的子事件生命周期。

    - 订阅：按模板的观测声明 acquire 可观测目标，自己就是订阅者（Dispatcher 直接回调）；
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
        """新装入模板：订阅并开始评估开启条件。模板须已编译通过（观测声明已校验）。"""
        runner = cls(parent_id, template, runtime, on_change)
        runner._subscribe()
        return runner

    @classmethod
    def restore(
        cls,
        parent_id: str,
        ref: TemplateRef,
        runtime: EventRuntime,
        on_change: Callable[[], None],
    ) -> "EventRunner":
        """重启恢复：重新编译当前 / 挂起版本、读回开启条件状态、接回活跃子事件、重新订阅。不写库。"""
        template = _load(runtime, ref.template_id, ref.version)
        pending = (
            _load(runtime, ref.template_id, ref.pending_version)
            if ref.pending_version is not None
            else None
        )
        runner = cls(
            parent_id,
            template,
            runtime,
            on_change,
            pending=pending,
            open_state=runtime.runner_states.get(parent_id, template.id),
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
        return self._runtime.events.history(self._parent_id, self._template.id)

    def to_ref(self) -> TemplateRef:
        return TemplateRef(
            template_id=self._template.id,
            version=self._template.version,
            pending_version=self._pending.version if self._pending else None,
        )

    # ------------------------------------------------------------ Referencer

    def on_observation(self, observation: Observation) -> None:
        if observation.observable_id not in self._observables:
            return

        opened = self._template.open_tree.evaluate(observation, self._open_state)
        if opened.state_patch:
            self._open_state = apply_state_patch(self._open_state, opened.state_patch)
            self._runtime.runner_states.save(self._parent_id, self._template.id, self._open_state)

        if self._active is None:
            if opened.outcome != HIT:
                return
            self._active = Event.open(
                self._parent_id,
                self._template,
                self._runtime,
                self.target_names,
                cycle=observation.occurred_at.year,
            )

        event = self._active
        event.process(observation)
        self._runtime.events.save(event.to_record())
        if event.is_closed:
            self._end_cycle()

    # ------------------------------------------------------------ 版本 / 生命周期

    def check_version(self, template: EventTemplate) -> None:
        latest = self._pending.version if self._pending else self._template.version
        if template.version <= latest:
            raise TemplateVersionError(
                f"{template.id}: version {template.version} <= latest {latest}"
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
        self._runtime.events.save(self._active.to_record())
        self._end_cycle()

    def dispose(self, reason: str) -> None:
        """模板被移除：关闭当前子事件、取消全部订阅、删除开启条件状态。"""
        if self._active is not None:
            self._active.close(reason)
            self._runtime.events.save(self._active.to_record())
            self._active = None
        for observable in self._observables.values():
            observable.release(self)
        self._observables = {}
        self._runtime.runner_states.remove(self._parent_id, self._template.id)

    # ------------------------------------------------------------ 内部

    def _end_cycle(self) -> None:
        self._active = None
        if self._pending is not None:
            self._switch(self._pending)

    def _switch(self, template: EventTemplate) -> None:
        """切换到新版本：开启条件树可能不同，状态清空；按新观测声明重新订阅。"""
        self._template = template
        self._pending = None
        self._open_state = {}
        self._runtime.runner_states.save(self._parent_id, template.id, self._open_state)
        self._subscribe()
        self._on_change()

    def _subscribe(self) -> None:
        """按当前模板的观测声明订阅；不再需要的可观测目标 release。"""
        subscribed: dict[str, ObservableTarget] = {}
        for o in self._template.observation_defs:
            observable = self._runtime.targets.get_observable(o.target_id, o.focus)
            observable.acquire(self, o.upstreams)
            subscribed[observable.id] = observable
        for oid, observable in self._observables.items():
            if oid not in subscribed:
                observable.release(self)
        self._observables = subscribed

    def _restore_active(self) -> Event | None:
        record = self._runtime.events.find_active(self._parent_id, self._template.id)
        if record is None:
            return None
        if record.template_version != self._template.version:
            # 不应出现（子事件总按当前版本运行）；防御性补关，避免孤儿活跃记录
            logger.error("active event %s has stale version; closing", record.id)
            self._runtime.events.save(
                record.model_copy(
                    update={"closed_at": datetime.now(UTC), "close_reason": "version_mismatch"}
                )
            )
            return None
        return Event(record, self._template, self._runtime, self.target_names)


def _load(runtime: EventRuntime, template_id: str, version: int) -> EventTemplate:
    template_def = runtime.templates.get(template_id, version)
    if template_def is None:
        raise TemplateNotFoundError(f"{template_id} v{version}")
    return EventTemplate.compile(
        template_def, runtime.conditions, runtime.operator_registry, runtime.targets
    )
