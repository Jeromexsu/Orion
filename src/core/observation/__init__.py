"""观测：观察点、观测、观测外壳——观测长什么样（输出契约）。

负责：观察点（名字 + 它返回的观测类）；观测（观察点返回的数据本身）；观测外壳（观测 + 来源信息，在管道里流动）。
      观察点与目标类型无关，多种目标类型可以共用同一个观察点。
对外：ObservedPoint / Observation 是插件继承的基类，@observed_point 声明；ObservationEnvelope 是观测外壳。
依赖：无（最底层）。
扩展点：plugins/observed_points/ 下继承 ObservedPoint + Observation。
"""

from core.observation.envelope import ObservationEnvelope
from core.observation.observed_point import (
    Observation,
    ObservedPoint,
    observed_point,
    observed_point_name,
)

__all__ = [
    "Observation",
    "ObservationEnvelope",
    "ObservedPoint",
    "observed_point",
    "observed_point_name",
]
