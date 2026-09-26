from collections.abc import Mapping
from typing import Protocol

from pydantic import BaseModel


class TargetType(Protocol):
    """一种目标类型（如飞机）。每种类型一个实现，放在 plugins/target/ 下。"""

    @property
    def name(self) -> str:
        """类型名，全局唯一，Target.type 引用它。"""
        ...

    @property
    def attributes_model(self) -> type[BaseModel]:
        """属性字段：校验 Target.attributes。"""
        ...

    @property
    def focuses(self) -> Mapping[str, type[BaseModel]]:
        """关注点字段：关注点名 → 该关注点下动态数据的 schema。"""
        ...
