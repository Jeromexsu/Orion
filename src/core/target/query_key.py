"""查询键：用什么去查一个目标（如 ICAO 地址、MMSI）。

与观察点对称：观察点是输出契约（上游返回什么），查询键是输入契约（上游拿什么去查）。
目标类型和 Adapter 都 import 同一个查询键类，不靠字段名字符串对齐。
"""

from functools import cache
from typing import Any, ClassVar

from pydantic import TypeAdapter


class QueryKey:
    """查询键：名字 + 取值的类型与格式。每种一个子类，放在 plugins/query_keys/ 下；不实例化。

        class Icao24(QueryKey):
            name: ClassVar[str] = "icao24"
            value_type: ClassVar[Any] = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{6}$")]

    目标类型在提供它的字段上标注：icao24: Annotated[str | None, Icao24] = None
    Adapter 用它声明支持的查询方式：query_key_sets = (frozenset({Icao24}),)
    """

    name: ClassVar[str]
    value_type: ClassVar[Any]


def query_key_name(query_key: type[QueryKey]) -> str:
    """读出查询键名，并检查子类把 name / value_type 都声明了。"""
    name = getattr(query_key, "name", None)
    if not isinstance(name, str) or not name:
        raise TypeError(f'{query_key.__name__} must set name: ClassVar[str] = "..."')
    if not hasattr(query_key, "value_type"):
        raise TypeError(f"{query_key.__name__} must set value_type")
    return name


def validate_query_value(query_key: type[QueryKey], value: Any) -> Any:
    """按查询键的 value_type 校验取值，返回校验后的值。不合法抛 pydantic.ValidationError。"""
    return _adapter(query_key).validate_python(value)


@cache
def _adapter(query_key: type[QueryKey]) -> TypeAdapter[Any]:
    return TypeAdapter(query_key.value_type)
