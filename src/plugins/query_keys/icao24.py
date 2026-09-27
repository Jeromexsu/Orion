"""示例查询键：ICAO 24 位地址（飞机应答机地址）。新增查询键照这个写。"""

from core.target import QueryKey, query_key


@query_key("icao24", pattern=r"^[0-9a-f]{6}$")
class Icao24(QueryKey):
    """6 位小写十六进制，如 "780a3b"。"""
