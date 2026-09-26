from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel


class TargetResolver(Protocol):
    """查 ObservableTarget 的动态数据 schema。由 target 的 TargetManager 结构化实现。"""

    def dynamic_schema(self, observable_id: str) -> type[BaseModel] | None: ...


class Observation(Protocol):
    """一条观测：ConditionTree.evaluate 的输入，也原样（只读）交给 LeafEvaluator。

    core.contracts.DynamicData 结构化满足它。
    """

    @property
    def observable_id(self) -> str: ...

    @property
    def fields(self) -> Mapping[str, Any]:
        """按关注点 dynamic schema 校验过的动态数据字段。"""
        ...

    @property
    def occurred_at(self) -> datetime:
        """发生时间（不是处理时间）；时间窗口类判断用它。"""
        ...
