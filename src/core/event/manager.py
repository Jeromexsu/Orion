import logging

from core.event.errors import DuplicateParentEventError, ParentEventNotFoundError
from core.event.parent import ParentEvent
from core.event.runtime import EventRuntime

logger = logging.getLogger(__name__)


class EventManager:
    """event 模块入口：创建、查找父事件，以及启动时的重启恢复。"""

    def __init__(self, runtime: EventRuntime) -> None:
        self._runtime = runtime
        self._parents: dict[str, ParentEvent] = {}

    def create(self, parent_id: str, name: str) -> ParentEvent:
        if parent_id in self._parents or self._runtime.parents.get(parent_id) is not None:
            raise DuplicateParentEventError(parent_id)
        parent = ParentEvent(parent_id, name, self._runtime)
        self._runtime.parents.upsert(parent.to_record())
        self._parents[parent_id] = parent
        return parent

    def get(self, parent_id: str) -> ParentEvent:
        try:
            return self._parents[parent_id]
        except KeyError:
            raise ParentEventNotFoundError(parent_id) from None

    def parents(self) -> list[ParentEvent]:
        return list(self._parents.values())

    def digest_all(self) -> list[str]:
        """调度器定时调用。单个父事件失败只记日志。返回失败的父事件 ID。"""
        failed: list[str] = []
        for parent in self._parents.values():
            try:
                parent.digest()
            except Exception:
                logger.exception("digest failed for parent event %s", parent.id)
                failed.append(parent.id)
        return failed

    def restore(self) -> list[str]:
        """启动时调用：全量加载父事件，各 slot 重新订阅（订阅关系不持久化）。

        单个父事件恢复失败只记日志，不影响其他。返回恢复失败的父事件 ID。
        """
        failed: list[str] = []
        for record in self._runtime.parents.list_all():
            if record.id in self._parents:
                continue
            try:
                self._parents[record.id] = ParentEvent.restore(record, self._runtime)
            except Exception:
                logger.exception("failed to restore parent event %s", record.id)
                failed.append(record.id)
        return failed
