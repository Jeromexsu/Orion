"""示例观察点：位置。飞机、船、车等都可以在这个观察点被观测。"""

from typing import ClassVar

from core.target import ObservedPoint


class Position(ObservedPoint):
    name: ClassVar[str] = "position"

    lat: float
    lon: float
    altitude_m: float | None = None   # 不是所有目标都有高度
