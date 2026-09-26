"""示例 TargetType：飞机。新增目标类型照这个写。"""

from pydantic import BaseModel


class AircraftAttributes(BaseModel):
    registration: str           # 注册号，如 "B-2447"
    icao24: str | None = None   # ICAO 24 位地址


class AircraftPosition(BaseModel):
    lat: float
    lon: float
    altitude_m: float | None = None


class AircraftType:
    name = "aircraft"
    attributes_model = AircraftAttributes
    focuses = {"position": AircraftPosition}
