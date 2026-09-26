"""event 模块的仓库接口，由 persistence 层实现，bootstrap 时注入。

与设计文档第九节的差别：仓库读写的是纯数据记录，而不是活对象——
活对象依赖条件引擎、算子注册表等运行时组件，持久化层不该去构造它们。
"""

from typing import Protocol

from core.event.definitions import TemplateDef
from core.event.records import InstanceRecord, ParentEventRecord


class ParentEventRepository(Protocol):
    def get(self, parent_id: str) -> ParentEventRecord | None: ...
    def upsert(self, parent: ParentEventRecord) -> None: ...
    def list_all(self) -> list[ParentEventRecord]: ...   # 重启恢复用


class TemplateRepository(Protocol):
    def get(self, template_id: str, version: int | None = None) -> TemplateDef | None: ...
    def upsert(self, template: TemplateDef) -> None: ...   # 新版本=新记录，绝不覆盖旧版本
    def list_versions(self, template_id: str) -> list[int]: ...


class InstanceRepository(Protocol):
    def find_active(self, parent_id: str, template_id: str) -> InstanceRecord | None: ...
    def save(self, instance: InstanceRecord) -> None: ...
    def history(self, parent_id: str, template_id: str) -> list[InstanceRecord]: ...
