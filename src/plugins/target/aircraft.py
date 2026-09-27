"""示例目标类型：飞机。新增目标类型照这个写。"""

from typing import ClassVar, Literal

from core.target import ObservedPoint, Target
from plugins.observed_points.position import Position


class Aircraft(Target, frozen=True):
    observed_points: ClassVar[tuple[type[ObservedPoint], ...]] = (Position,)

    type: Literal["aircraft"] = "aircraft"
    registration: str           # 注册号，如 "B-2447"
    icao24: str | None = None   # ICAO 24 位地址
