from typing import Any, Protocol

from pydantic import BaseModel


class TargetResolver(Protocol):
    """查 ObservableTarget 的动态数据 schema。由 target 的 TargetManager 结构化实现。"""

    def dynamic_schema(self, observable_id: str) -> type[BaseModel] | None: ...


class Observation(Protocol):
    """ConditionTree.evaluate 的输入。target 的 DynamicData 结构化满足它。"""

    @property
    def observable_id(self) -> str: ...

    @property
    def fields(self) -> dict[str, Any]: ...
