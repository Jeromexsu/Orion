"""目标：静态目标——目标类型、目标记录、查询键。

负责：目标类型（插件，声明能在哪些观察点被观测、哪些字段提供哪些查询键）与目标记录的生命周期；
      查询键（输入契约：拿什么去查一个目标）。
对外：TargetManager 是入口（目标实例的增删改查）；TargetTypeRegistry 是目标类型的注册表（顺带收集观察点）；
      Target / QueryKey 是插件继承的基类。
依赖：observation（目标类型声明观察点）。
扩展点：plugins/target/ 下继承 Target；plugins/query_keys/ 下继承 QueryKey。
"""

from core.target.errors import (
    DuplicateObservedPointError,
    DuplicateTargetTypeError,
    TargetError,
    TargetNotFoundError,
    TargetTypeChangeError,
    UnknownObservedPointError,
    UnknownTargetTypeError,
)
from core.target.manager import TargetManager
from core.target.query_key import (
    QueryKey,
    provides,
    query_key,
    query_key_name,
    validate_query_value,
)
from core.target.registry import TargetTypeRegistry
from core.target.repository import TargetRepository
from core.target.target import Target, TargetRecord, target_type, type_name

__all__ = [
    "DuplicateObservedPointError",
    "DuplicateTargetTypeError",
    "QueryKey",
    "Target",
    "TargetError",
    "TargetManager",
    "TargetNotFoundError",
    "TargetRecord",
    "TargetRepository",
    "TargetTypeChangeError",
    "TargetTypeRegistry",
    "UnknownObservedPointError",
    "UnknownTargetTypeError",
    "provides",
    "query_key",
    "query_key_name",
    "target_type",
    "type_name",
    "validate_query_value",
]
