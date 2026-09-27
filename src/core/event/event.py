import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from core.condition_engine import HIT, apply_state_patch
from core.event.definitions import OperatorMountDef
from core.event.errors import EventClosedError
from core.event.records import EventRecord
from core.event.runtime import EventRuntime
from core.event.template import EventTemplate
from core.operators import Trigger, build_context
from core.target import ObservationEnvelope

logger = logging.getLogger(__name__)

# 推进类算子把这个状态键置为 True 表示子事件收敛、该关闭了
CLOSE_STATUS_KEY = "closed"


def _now() -> datetime:
    return datetime.now(UTC)


class Event:
    """子事件：模板的一次运行（一个周期）。由 EventRunner 创建、喂数据、存档。

    状态变更的唯一入口是 update_status，只经 ProgressContext 由推进类算子调用。
    """

    def __init__(
        self,
        event_id: str,
        parent_id: str,
        template: EventTemplate,
        cycle: int,
        runtime: EventRuntime,
        target_names: Callable[[], Mapping[str, str]],
        *,
        opened_at: datetime,
        status: dict[str, Any] | None = None,
        condition_state: dict[str, dict[str, Any]] | None = None,
        closed_at: datetime | None = None,
        close_reason: str | None = None,
    ) -> None:
        self._id = event_id
        self._parent_id = parent_id
        self._template = template
        self._cycle = cycle
        self._runtime = runtime
        self._target_names = target_names
        self._opened_at = opened_at
        self._status: dict[str, Any] = status or {}
        self._condition_state: dict[str, dict[str, Any]] = condition_state or {}
        self._closed_at = closed_at
        self._close_reason = close_reason
        self._in_status_hooks = False

    @classmethod
    def open(
        cls,
        parent_id: str,
        template: EventTemplate,
        cycle: int,
        runtime: EventRuntime,
        target_names: Callable[[], Mapping[str, str]],
    ) -> "Event":
        """新建子事件并跑 created 钩子，返回它。不写库（由 runner 存档）。"""
        event = cls(
            uuid4().hex, parent_id, template, cycle, runtime, target_names, opened_at=_now()
        )
        event._run_hooks(template.hooks_at("created"), Trigger(mount_point="created"))
        return event

    @classmethod
    def restore(
        cls,
        record: EventRecord,
        template: EventTemplate,
        runtime: EventRuntime,
        target_names: Callable[[], Mapping[str, str]],
    ) -> "Event":
        """重启恢复：从记录还原状态，不跑钩子、不写库。记录必须属于这个模板版本，否则抛 ValueError。"""
        if (record.template_id, record.template_version) != (template.id, template.version):
            raise ValueError(
                f"event {record.id} does not belong to template {template.id} v{template.version}"
            )
        return cls(
            record.id,
            record.parent_id,
            template,
            record.cycle,
            runtime,
            target_names,
            opened_at=record.opened_at,
            status=dict(record.status),
            condition_state=dict(record.condition_state),
            closed_at=record.closed_at,
            close_reason=record.close_reason,
        )

    # ------------------------------------------------------------ 只读

    @property
    def id(self) -> str:
        return self._id

    @property
    def template(self) -> EventTemplate:
        return self._template

    @property
    def cycle(self) -> int:
        return self._cycle

    @property
    def status(self) -> Mapping[str, Any]:
        return dict(self._status)

    @property
    def is_closed(self) -> bool:
        return self._closed_at is not None

    def to_record(self) -> EventRecord:
        """当前状态的持久化记录。"""
        return EventRecord(
            id=self._id,
            parent_id=self._parent_id,
            template_id=self._template.id,
            template_version=self._template.version,
            cycle=self._cycle,
            status=dict(self._status),
            condition_state=dict(self._condition_state),
            opened_at=self._opened_at,
            closed_at=self._closed_at,
            close_reason=self._close_reason,
        )

    # ------------------------------------------------------------ 管道

    def process(self, envelope: ObservationEnvelope) -> None:
        """处理一条观测：pre 钩子 → 逐条规则跑条件树、合并条件状态、命中则跑规则钩子 → post 钩子
        → 状态表示收敛（should_close）就关闭。

        只改内存，不写库（由 runner 存档）。已关闭抛 EventClosedError。
        """
        if self.is_closed:
            raise EventClosedError(self._id)

        self._run_hooks(self._template.hooks_at("pre"), Trigger(mount_point="pre", envelope=envelope))

        for rule in self._template.rules:
            state = self._condition_state.get(rule.name, {})
            result = rule.tree.evaluate(envelope, state)
            if result.state_patch:
                self._condition_state[rule.name] = apply_state_patch(state, result.state_patch)
            if result.outcome == HIT:
                self._run_hooks(
                    rule.hook_defs, Trigger(mount_point="rule_hit", envelope=envelope, result=result)
                )

        self._run_hooks(self._template.hooks_at("post"), Trigger(mount_point="post", envelope=envelope))

        if self.should_close():
            self.close("converged")

    def update_status(self, patch: dict[str, Any]) -> None:
        """状态变更的唯一入口：把 patch 合并进状态，之后跑 status_updated 钩子。

        钩子里再调 update_status 只合并、不再触发钩子，避免无限递归。已关闭抛 EventClosedError。
        """
        if self.is_closed:
            raise EventClosedError(self._id)
        self._status.update(patch)
        if self._in_status_hooks:
            return
        self._in_status_hooks = True
        try:
            self._run_hooks(
                self._template.hooks_at("status_updated"),
                Trigger(mount_point="status_updated", patch=dict(patch)),
            )
        finally:
            self._in_status_hooks = False

    def should_close(self) -> bool:
        """推进类算子是否已把状态 CLOSE_STATUS_KEY 置为 True。"""
        return self._status.get(CLOSE_STATUS_KEY) is True

    def close(self, reason: str) -> None:
        """跑 closed 钩子后关闭。重复关闭忽略。不写库（由 runner 存档）。"""
        if self.is_closed:
            return
        self._run_hooks(self._template.hooks_at("closed"), Trigger(mount_point="closed"))
        self._closed_at = _now()
        self._close_reason = reason

    # ------------------------------------------------------------ 内部

    def _run_hooks(self, mounts: tuple[OperatorMountDef, ...], trigger: Trigger) -> None:
        """按挂载顺序同步执行，每个算子单独隔离异常。
        TODO: 标记为异步的输出类算子改为入队（见设计文档第三节）。"""
        for mount in mounts:
            operator = self._runtime.operator_registry.get(mount.operator)
            ctx = build_context(
                operator.category,
                state=self._status,
                params=mount.params,
                target_names=self._target_names(),
                update_status=self.update_status,
                suggest=self._runtime.suggestion_sink.receive,
                parent_id=self._parent_id,
                event_id=self._id,
            )
            try:
                operator.run(trigger, ctx)
            except Exception:
                logger.exception(
                    "operator %s failed at %s on event %s",
                    mount.operator,
                    trigger.mount_point,
                    self._id,
                )
