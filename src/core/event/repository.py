"""event 模块和 repo 层之间的契约：持久化记录 + 仓库接口（由 persistence 层实现，bootstrap 时注入）。

与设计文档第九节的差别：仓库读写的是纯数据记录，而不是活对象——
活对象依赖条件引擎、钩子注册表等运行时组件，持久化层不该去构造它们。活对象由 ParentEventManager 从记录重建。
"""

from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from core.event.definitions import TemplateDef


class TemplateRef(BaseModel):
    """父事件记录里对一个模板的引用：用哪个版本，有没有挂起的新版本。"""

    model_config = ConfigDict(frozen=True)

    template_id: str
    version: int                        # 当前运行的版本
    pending_version: int | None = None  # 已发布、等当前子事件关闭后生效的新版本


class ParentEventRecord(BaseModel):
    """父事件是静态的：目标命名空间 + 模板集合。"""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    targets: list[str] = Field(default_factory=list[str])   # 目标命名空间（target_id）
    templates: list[TemplateRef] = Field(default_factory=list[TemplateRef])


class EventRecord(BaseModel):
    """子事件的持久化记录。closed_at 为空即活跃。"""

    model_config = ConfigDict(frozen=True)

    id: str
    parent_id: str
    template_id: str
    template_version: int
    cycle: int                                      # 周期标识：触发开启的那条数据发生的年份
    condition_state: dict[str, dict[str, Any]]      # 规则名 → 条件树状态，钩子不可见
    hook_state: dict[str, dict[str, Any]]           # 挂载名 → 那个挂载的钩子状态
    opened_at: datetime
    closed_at: datetime | None = None
    close_reason: str | None = None


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
