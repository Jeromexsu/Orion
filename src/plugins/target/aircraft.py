"""示例目标类型：飞机。新增目标类型照这个写。"""

from typing import Annotated, ClassVar, Literal

from core.target import ObservedPoint, Target
from plugins.observed_points.position import Position
from plugins.query_keys.icao24 import Icao24
from plugins.query_keys.registration import Registration


class Aircraft(Target, frozen=True):
    """飞机：可在位置观察点被观测；可按注册号或 ICAO 地址查询。"""

    observed_points: ClassVar[tuple[type[ObservedPoint], ...]] = (Position,)

    type: Literal["aircraft"] = "aircraft"
    registration: Annotated[str, Registration]      # 注册号，如 "B-2447"
    icao24: Annotated[str | None, Icao24] = None    # ICAO 24 位地址
