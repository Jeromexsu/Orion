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
from core.target import DynamicData

logger = logging.getLogger(__name__)

# 推进类算子把这个状态键置为 True 表示子事件收敛、该关闭了
CLOSE_STATUS_KEY = "closed"


def _now() -> datetime:
    return datetime.now(UTC)


class Event:
    """子事件：模板的一次运行（一个周期）。状态变更的唯一入口是 update_status，只由它自己（经 ProgressContext）调用。"""

    def __init__(
        self,
        record: EventRecord,
        template: EventTemplate,
        runtime: EventRuntime,
        target_names: Callable[[], Mapping[str, str]],
    ) -> None:
        if (record.template_id, record.template_version) != (template.id, template.version):
            raise ValueError(f"instance {record.id} does not belong to template {template.id} v{template.version}")
        self._id = record.id
        self._parent_id = record.parent_id
        self._template = template
        self._runtime = runtime
        self._target_names = target_names
        self._status: dict[str, Any] = dict(record.status)
        self._condition_state: dict[str, dict[str, Any]] = dict(record.condition_state)
        self._cycle = record.cycle
        self._opened_at = record.opened_at
        self._closed_at = record.closed_at
        self._close_reason = record.close_reason
        self._in_status_hooks = False

    @classmethod
    def open(
        cls,
        parent_id: str,
        template: EventTemplate,
        runtime: EventRuntime,
        target_names: Callable[[], Mapping[str, str]],
        cycle: int,
    ) -> "Event":
        """新建子事件并跑 created 钩子。"""
        record = EventRecord(
            id=uuid4().hex,
            parent_id=parent_id,
            template_id=template.id,
            template_version=template.version,
            cycle=cycle,
            status={},
            condition_state={},
            opened_at=_now(),
        )
        instance = cls(record, template, runtime, target_names)
        instance._run_hooks(template.hooks_at("created"), Trigger(mount_point="created"))
        return instance

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

    def process(self, data: DynamicData) -> None:
        """前置钩子 → 逐条规则跑条件树 → 合并 state_patch → 命中则跑规则钩子 → 后置钩子 → shouldClose。"""
        if self.is_closed:
            raise EventClosedError(self._id)

        self._run_hooks(self._template.hooks_at("pre"), Trigger(mount_point="pre", data=data))

        for rule in self._template.rules:
            state = self._condition_state.get(rule.name, {})
            result = rule.tree.evaluate(data, state)
            if result.state_patch:
                self._condition_state[rule.name] = apply_state_patch(state, result.state_patch)
            if result.outcome == HIT:
                self._run_hooks(
                    rule.hook_defs, Trigger(mount_point="rule_hit", data=data, result=result)
                )

        self._run_hooks(self._template.hooks_at("post"), Trigger(mount_point="post", data=data))

        if self.should_close():
            self.close("converged")

    def update_status(self, patch: dict[str, Any]) -> None:
        """状态变更的唯一入口。之后跑 status_updated 钩子；
        钩子里再调 update_status 只合并、不再触发钩子，避免无限递归。"""
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
        return self._status.get(CLOSE_STATUS_KEY) is True

    def close(self, reason: str) -> None:
        """跑 closed 钩子后关闭。重复关闭忽略。"""
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
                suggest=self._runtime.suggestions.receive,
                parent_id=self._parent_id,
                event_id=self._id,
            )
            try:
                operator.run(trigger, ctx)
            except Exception:
                logger.exception(
                    "operator %s failed at %s on instance %s",
                    mount.operator,
                    trigger.mount_point,
                    self._id,
                )
