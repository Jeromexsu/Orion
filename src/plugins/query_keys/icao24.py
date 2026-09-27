"""示例查询键：ICAO 24 位地址（飞机应答机地址）。新增查询键照这个写。"""

from typing import Annotated, Any, ClassVar

from pydantic import StringConstraints

from core.target import QueryKey


class Icao24(QueryKey):
    """6 位小写十六进制，如 "780a3b"。"""

    name: ClassVar[str] = "icao24"
    value_type: ClassVar[Any] = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{6}$")]
