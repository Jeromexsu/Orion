"""示例目标类型：飞机。新增目标类型照这个写。"""

from collections.abc import Mapping
from typing import ClassVar, Literal

from pydantic import BaseModel

from core.target import Target


class AircraftPosition(BaseModel):
    lat: float
    lon: float
    altitude_m: float | None = None


class Aircraft(Target, frozen=True):
    focuses: ClassVar[Mapping[str, type[BaseModel]]] = {"position": AircraftPosition}

    type: Literal["aircraft"] = "aircraft"
    registration: str           # 注册号，如 "B-2447"
    icao24: str | None = None   # ICAO 24 位地址
