"""event 模块的仓库接口，由 persistence 层实现，bootstrap 时注入。

与设计文档第九节的差别：仓库读写的是纯数据记录，而不是活对象——
活对象依赖条件引擎、算子注册表等运行时组件，持久化层不该去构造它们。
"""

from typing import Any, Protocol

from core.event.definitions import TemplateDef
from core.event.records import EventRecord, ParentEventRecord


class ParentEventRepository(Protocol):
    """父事件记录：目标命名空间 + 模板引用。"""

    def get(self, parent_id: str) -> ParentEventRecord | None:
        """不存在返回 None。"""
        ...

    def upsert(self, parent: ParentEventRecord) -> None:
        """按 id 新建或覆盖。"""
        ...

    def list_all(self) -> list[ParentEventRecord]:
        """全部父事件，重启恢复用。"""
        ...


class TemplateRepository(Protocol):
    """模板定义，按 (template_id, version) 存。新版本 = 新记录，绝不覆盖旧版本。"""

    def get(self, template_id: str, version: int | None = None) -> TemplateDef | None:
        """指定版本；不给 version 取最新版本。不存在返回 None。"""
        ...

    def upsert(self, template: TemplateDef) -> None:
        """保存一个版本。同一版本再存相同内容无影响；内容不同应拒绝。"""
        ...

    def list_versions(self, template_id: str) -> list[int]:
        """已存的全部版本号，升序。"""
        ...


class EventRepository(Protocol):
    """子事件记录，活跃的和已关闭的都在。"""

    def find_active(self, parent_id: str, template_id: str) -> EventRecord | None:
        """未关闭的那条（最多一条）；没有返回 None。"""
        ...

    def save(self, record: EventRecord) -> None:
        """按 id 新建或覆盖。"""
        ...

    def history(self, parent_id: str, template_id: str) -> list[EventRecord]:
        """全部子事件记录，按开启时间排序。"""
        ...


class RunnerStateRepository(Protocol):
    """runner 的开启条件状态，按 (父事件, 模板) 存。年度事件跨越多次重启，必须持久化。"""

    def get(self, parent_id: str, template_id: str) -> dict[str, Any] | None:
        """没存过返回 None。"""
        ...

    def save(self, parent_id: str, template_id: str, state: dict[str, Any]) -> None:
        """覆盖保存。"""
        ...

    def remove(self, parent_id: str, template_id: str) -> None:
        """模板移除时删除。不存在时忽略。"""
        ...
