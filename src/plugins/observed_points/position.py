"""示例观察点：位置。飞机、船、车等都可以在这个观察点被观测。"""

from typing import ClassVar

from core.target import Observation, ObservedPoint


class PositionObservation(Observation):
    """位置观测的形状。"""

    lat: float
    lon: float
    altitude_m: float | None = None   # 不是所有目标都有高度


class Position(ObservedPoint):
    """位置观察点：名字 "position"，返回 PositionObservation。"""

    name: ClassVar[str] = "position"
    observation: ClassVar[type[Observation]] = PositionObservation
