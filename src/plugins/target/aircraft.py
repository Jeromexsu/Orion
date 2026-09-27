"""示例目标类型：飞机。新增目标类型照这个写。"""

from core.target import Target, provides, target_type
from plugins.observed_points.position import Position
from plugins.query_keys.icao24 import Icao24
from plugins.query_keys.registration import Registration


@target_type("aircraft", observed_points=[Position])
class Aircraft(Target):
    """飞机：可在位置观察点被观测；可按注册号或 ICAO 地址查询。"""

    registration: str = provides(Registration)             # 注册号，如 "B-2447"
    icao24: str | None = provides(Icao24, default=None)    # ICAO 24 位地址
