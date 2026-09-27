"""示例查询键：航空器注册号。"""

from typing import Annotated, Any, ClassVar

from pydantic import StringConstraints

from core.target import QueryKey


class Registration(QueryKey):
    """注册号，如 "B-2447"。"""

    name: ClassVar[str] = "registration"
    value_type: ClassVar[Any] = Annotated[str, StringConstraints(min_length=1)]
