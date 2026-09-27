"""查询键：用什么去查一个目标（如 ICAO 地址、MMSI）。

与观察点对称：观察点是输出契约（上游返回什么），查询键是输入契约（上游拿什么去查）。
目标类型和 UpstreamAdapter 都 import 同一个查询键类，不靠字段名字符串对齐。
"""

from collections.abc import Callable
from functools import cache
from typing import Annotated, Any, ClassVar, TypeVar

from pydantic import Field, StringConstraints, TypeAdapter
from pydantic_core import PydanticUndefined


class QueryKey:
    """查询键：名字 + 取值的类型与格式。每种一个子类，放在 plugins/query_keys/ 下，用 @query_key 声明；不实例化。

        @query_key("icao24", pattern=r"^[0-9a-f]{6}$")
        class Icao24(QueryKey): ...

    目标类型在提供它的字段上关联：icao24: str | None = provides(Icao24, default=None)
    UpstreamAdapter 用它声明支持的查询方式：query_key_sets = (frozenset({Icao24}),)
    """

    name: ClassVar[str]         # 由 @query_key 设置
    value_type: ClassVar[Any]   # 由 @query_key 设置


K = TypeVar("K", bound=QueryKey)


def query_key(
    name: str, *, pattern: str | None = None, value_type: Any = str
) -> Callable[[type[K]], type[K]]:
    """声明一个查询键：名字 + 取值格式。

    常见的字符串格式用 pattern 给正则；其他类型或约束用 value_type（如 int、Annotated[...]）。
    """

    def decorate(cls: type[K]) -> type[K]:
        if not name:
            raise TypeError(f"{cls.__name__}: query key name must not be empty")
        if pattern is not None and value_type is not str:
            raise TypeError(f"{cls.__name__}: pattern only applies to str values")
        cls.name = name
        cls.value_type = (
            Annotated[str, StringConstraints(pattern=pattern)] if pattern is not None else value_type
        )
        return cls

    return decorate


def provides(key: type[QueryKey], *, default: Any = PydanticUndefined) -> Any:
    """在目标类型的字段上关联查询键：mmsi: str = provides(Mmsi)——这个字段提供查询键 Mmsi。

    不给 default 即必填；可为空的写 provides(Imo, default=None)。
    （等价于 Annotated[str, Mmsi]；字段的元数据里记下查询键，Target.query_key_fields 据此读出。）
    """
    info = Field(default=default)
    info.metadata.append(key)
    return info


def query_key_name(query_key: type[QueryKey]) -> str:
    """读出查询键名，并检查子类把 name / value_type 都声明了。"""
    name = getattr(query_key, "name", None)
    if not isinstance(name, str) or not name:
        raise TypeError(f'{query_key.__name__} must be declared with @query_key("...")')
    if not hasattr(query_key, "value_type"):
        raise TypeError(f"{query_key.__name__} must set value_type")
    return name


def validate_query_value(query_key: type[QueryKey], value: Any) -> Any:
    """按查询键的 value_type 校验取值，返回校验后的值。不合法抛 pydantic.ValidationError。"""
    return _adapter(query_key).validate_python(value)


@cache
def _adapter(query_key: type[QueryKey]) -> TypeAdapter[Any]:
    return TypeAdapter(query_key.value_type)
