"""示例观察点：位置。飞机、船、车等都可以在这个观察点被观测。新增观察点照这个写。"""

from core.target import Observation, ObservedPoint, observed_point


class PositionObservation(Observation):
    """位置观测的形状。"""

    lat: float
    lon: float
    altitude_m: float | None = None   # 不是所有目标都有高度


@observed_point("position", observation=PositionObservation)
class Position(ObservedPoint):
    """位置。"""
