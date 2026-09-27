"""观察点：观测的形状。与目标类型无关，不同目标类型可以共用同一个观察点。"""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class ObservedPoint(BaseModel):
    """所有观察点的基类。每个观察点一个子类，放在 plugins/observed_points/ 下。

    子类用 name 给出观察点名（如 "position"），用普通字段声明观测 fields 的形状（即动态数据的 schema）：

        class Position(ObservedPoint):
            name: ClassVar[str] = "position"
            lat: float
            lon: float
    """

    model_config = ConfigDict(frozen=True)

    name: ClassVar[str]


def observed_point_name(observed_point: type[ObservedPoint]) -> str:
    """读出观察点名；子类忘了给 name 时报错。"""
    name = getattr(observed_point, "name", None)
    if not isinstance(name, str) or not name:
        raise TypeError(f'{observed_point.__name__} must set name: ClassVar[str] = "..."')
    return name
