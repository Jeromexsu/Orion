import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from core.condition_engine import apply_state_patch
from core.contracts import HIT, DynamicData
from core.event.errors import TemplateNotFoundError, TemplateVersionError
from core.event.instance import SubEventInstance
from core.event.records import InstanceRecord, TemplateRef
from core.event.runtime import EventRuntime
from core.event.template import SubEventTemplate
from core.target import ObservableTarget, TargetManager, UnsupportedUpstreamError

logger = logging.getLogger(__name__)


def check_observations(template: SubEventTemplate, targets: TargetManager) -> None:
    """装入模板前检查观测声明可订阅：目标与关注点存在、上游可用。不产生订阅。"""
    for o in template.observations:
        observable = targets.get_observable(o.target_id, o.focus)
        unknown = set(o.upstreams) - set(observable.upstreams)
        if unknown:
            raise UnsupportedUpstreamError(
                f"{observable.id}: {sorted(unknown)} not in available upstreams "
                f"{list(observable.upstreams)}"
            )


class SubEventSlot:
    """运行中的模板：管理这个模板的子事件生命周期。

    - 订阅：按模板的观测声明 acquire 可观测目标，自己就是订阅者（Dispatcher 直接回调）；
    - 开启：每条数据都评估开启条件并更新其状态；无活跃实例且命中时开新实例，并把该条数据交给它；
    - 运行：有活跃实例时数据交给实例处理（同一模板最多一个活跃实例）；
    - 换版本：新版本只对下一个周期生效——有活跃实例时挂起，实例关闭后切换并重新订阅；
    - 存档：实例记录每处理一条数据就存；开启条件状态单独持久化（年度事件跨越多次重启）。
    """

    def __init__(
        self,
        parent_id: str,
        template: SubEventTemplate,
        runtime: EventRuntime,
        on_change: Callable[[], None],
        *,
        pending: SubEventTemplate | None = None,
        open_state: dict[str, Any] | None = None,
        active: SubEventInstance | None = None,
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
        template: SubEventTemplate,
        runtime: EventRuntime,
        on_change: Callable[[], None],
    ) -> "SubEventSlot":
        """新装入模板：订阅并开始评估开启条件。调用前应已 check_observations。"""
        slot = cls(parent_id, template, runtime, on_change)
        slot._subscribe()
        return slot

    @classmethod
    def restore(
        cls,
        parent_id: str,
        ref: TemplateRef,
        runtime: EventRuntime,
        on_change: Callable[[], None],
    ) -> "SubEventSlot":
        """重启恢复：重新编译当前 / 挂起版本、读回开启条件状态、接回活跃实例、重新订阅。不写库。"""
        template = _load(runtime, ref.template_id, ref.version)
        pending = (
            _load(runtime, ref.template_id, ref.pending_version)
            if ref.pending_version is not None
            else None
        )
        slot = cls(
            parent_id,
            template,
            runtime,
            on_change,
            pending=pending,
            open_state=runtime.slot_states.get(parent_id, template.id),
        )
        slot._active = slot._restore_active()
        slot._subscribe()
        return slot

    # ------------------------------------------------------------ 只读

    @property
    def template(self) -> SubEventTemplate:
        return self._template

    @property
    def pending(self) -> SubEventTemplate | None:
        return self._pending

    @property
    def active(self) -> SubEventInstance | None:
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

    def history(self) -> list[InstanceRecord]:
        return self._runtime.instances.history(self._parent_id, self._template.id)

    def to_ref(self) -> TemplateRef:
        return TemplateRef(
            template_id=self._template.id,
            version=self._template.version,
            pending_version=self._pending.version if self._pending else None,
        )

    # ------------------------------------------------------------ Referencer

    def on_data(self, data: DynamicData) -> None:
        if data.observable_id not in self._observables:
            return

        opened = self._template.open_tree.evaluate(data, self._open_state)
        if opened.state_patch:
            self._open_state = apply_state_patch(self._open_state, opened.state_patch)
            self._runtime.slot_states.save(self._parent_id, self._template.id, self._open_state)

        if self._active is None:
            if opened.outcome != HIT:
                return
            self._active = SubEventInstance.open(
                self._parent_id,
                self._template,
                self._runtime,
                self.target_names,
                cycle=data.occurred_at.year,
            )

        instance = self._active
        instance.process(data)
        self._runtime.instances.save(instance.to_record())
        if instance.is_closed:
            self._end_cycle()

    # ------------------------------------------------------------ 版本 / 生命周期

    def check_version(self, template: SubEventTemplate) -> None:
        latest = self._pending.version if self._pending else self._template.version
        if template.version <= latest:
            raise TemplateVersionError(
                f"{template.id}: version {template.version} <= latest {latest}"
            )

    def stage(self, template: SubEventTemplate) -> None:
        """发布新版本：无活跃实例立即切换，否则挂起到当前实例关闭。调用前应已 check_version。"""
        if self._active is None:
            self._switch(template)
        else:
            self._pending = template
            self._on_change()

    def close_active(self, reason: str) -> None:
        """手动关闭当前实例（如分析师判定本周期结束），之后按挂起版本切换。"""
        if self._active is None:
            return
        self._active.close(reason)
        self._runtime.instances.save(self._active.to_record())
        self._end_cycle()

    def dispose(self, reason: str) -> None:
        """模板被移除：关闭当前实例、取消全部订阅、删除开启条件状态。"""
        if self._active is not None:
            self._active.close(reason)
            self._runtime.instances.save(self._active.to_record())
            self._active = None
        for observable in self._observables.values():
            observable.release(self)
        self._observables = {}
        self._runtime.slot_states.remove(self._parent_id, self._template.id)

    # ------------------------------------------------------------ 内部

    def _end_cycle(self) -> None:
        self._active = None
        if self._pending is not None:
            self._switch(self._pending)

    def _switch(self, template: SubEventTemplate) -> None:
        """切换到新版本：开启条件树可能不同，状态清空；按新观测声明重新订阅。"""
        self._template = template
        self._pending = None
        self._open_state = {}
        self._runtime.slot_states.save(self._parent_id, template.id, self._open_state)
        self._subscribe()
        self._on_change()

    def _subscribe(self) -> None:
        """按当前模板的观测声明订阅；不再需要的可观测目标 release。"""
        subscribed: dict[str, ObservableTarget] = {}
        for o in self._template.observations:
            observable = self._runtime.targets.get_observable(o.target_id, o.focus)
            observable.acquire(self, o.upstreams)
            subscribed[observable.id] = observable
        for oid, observable in self._observables.items():
            if oid not in subscribed:
                observable.release(self)
        self._observables = subscribed

    def _restore_active(self) -> SubEventInstance | None:
        record = self._runtime.instances.find_active(self._parent_id, self._template.id)
        if record is None:
            return None
        if record.template_version != self._template.version:
            # 不应出现（实例总按当前版本运行）；防御性补关，避免孤儿活跃记录
            logger.error("active instance %s has stale version; closing", record.id)
            self._runtime.instances.save(
                record.model_copy(
                    update={"closed_at": datetime.now(UTC), "close_reason": "version_mismatch"}
                )
            )
            return None
        return SubEventInstance(record, self._template, self._runtime, self.target_names)


def _load(runtime: EventRuntime, template_id: str, version: int) -> SubEventTemplate:
    definition = runtime.templates.get(template_id, version)
    if definition is None:
        raise TemplateNotFoundError(f"{template_id} v{version}")
    return SubEventTemplate.compile(definition, runtime.conditions, runtime.operators)
