"""观察点与观测。观察点与目标类型无关，不同目标类型可以共用同一个观察点。"""

from collections.abc import Callable
from typing import ClassVar, TypeVar

from pydantic import BaseModel, ConfigDict


class Observation(BaseModel):
    """观测：观察点观察之后返回的数据。每个观察点一个子类，字段就是观测的形状：

        class PositionObservation(Observation):
            lat: float
            lon: float
    """

    model_config = ConfigDict(frozen=True)


class ObservedPoint:
    """观察点：名字 + 它返回什么观测。每个观察点一个子类，放在 plugins/observed_points/ 下，
    用 @observed_point 声明；不实例化。

        @observed_point("position", observation=PositionObservation)
        class Position(ObservedPoint): ...
    """

    name: ClassVar[str]                         # 由 @observed_point 设置
    observation: ClassVar[type[Observation]]    # 由 @observed_point 设置


P = TypeVar("P", bound=ObservedPoint)


def observed_point(
    name: str, *, observation: type[Observation]
) -> Callable[[type[P]], type[P]]:
    """声明一个观察点：名字 + 返回什么观测。"""

    def decorate(cls: type[P]) -> type[P]:
        if not name:
            raise TypeError(f"{cls.__name__}: observed point name must not be empty")
        cls.name = name
        cls.observation = observation
        observed_point_name(cls)
        return cls

    return decorate


def observed_point_name(observed_point: type[ObservedPoint]) -> str:
    """读出观察点名，并检查子类把 name / observation 都声明了。"""
    name = getattr(observed_point, "name", None)
    if not isinstance(name, str) or not name:
        raise TypeError(f'{observed_point.__name__} must be declared with @observed_point("...")')
    observation = getattr(observed_point, "observation", None)
    if not (isinstance(observation, type) and issubclass(observation, Observation)):
        raise TypeError(f"{observed_point.__name__} must set observation to an Observation subclass")
    return name
