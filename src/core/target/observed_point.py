"""观察点与观测。观察点与目标类型无关，不同目标类型可以共用同一个观察点。"""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class Observation(BaseModel):
    """观测：观察点观察之后返回的数据。每个观察点一个子类，字段就是观测的形状：

        class PositionObservation(Observation):
            lat: float
            lon: float
    """

    model_config = ConfigDict(frozen=True)


class ObservedPoint:
    """观察点：名字 + 它返回什么观测。每个观察点一个子类，放在 plugins/observed_points/ 下；不实例化。

        class Position(ObservedPoint):
            name: ClassVar[str] = "position"
            observation: ClassVar[type[Observation]] = PositionObservation
    """

    name: ClassVar[str]
    observation: ClassVar[type[Observation]]


def observed_point_name(observed_point: type[ObservedPoint]) -> str:
    """读出观察点名，并检查子类把 name / observation 都声明了。"""
    name = getattr(observed_point, "name", None)
    if not isinstance(name, str) or not name:
        raise TypeError(f'{observed_point.__name__} must set name: ClassVar[str] = "..."')
    observation = getattr(observed_point, "observation", None)
    if not (isinstance(observation, type) and issubclass(observation, Observation)):
        raise TypeError(f"{observed_point.__name__} must set observation to an Observation subclass")
    return name
