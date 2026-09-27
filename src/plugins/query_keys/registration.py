"""示例查询键：航空器注册号。"""

from core.target import QueryKey, query_key


@query_key("registration", pattern=r"^\S+$")
class Registration(QueryKey):
    """注册号，如 "B-2447"。"""
