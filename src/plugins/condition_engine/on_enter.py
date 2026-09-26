"""示例 Evaluator：进入区域。有状态的判断方式照这个写。"""

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field

from core.condition_engine import Evaluator, Observation
from core.contracts import HIT, MISS, EvalResult

Point = tuple[float, float]                 # (lat, lon)
Polygon = list[Point]


def point_in_polygon(point: Point, polygon: Polygon) -> bool:
    """射线法。平面近似，适合小范围区域。"""
    lat, lon = point
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        lat_i, lon_i = polygon[i]
        lat_j, lon_j = polygon[j]
        if (lon_i > lon) != (lon_j > lon) and lat < (lat_j - lat_i) * (lon - lon_i) / (
            lon_j - lon_i
        ) + lat_i:
            inside = not inside
        j = i
    return inside


class OnEnterParams(BaseModel):
    area: Polygon = Field(min_length=3)
    initial_as_enter: bool = False   # 首次观测就在区域内是否算“进入”


class OnEnter(Evaluator[OnEnterParams]):
    type = "onEnter"
    requires = frozenset({"lat", "lon"})
    params_model = OnEnterParams

    def evaluate(
        self, params: OnEnterParams, obs: Observation, state: Mapping[str, Any]
    ) -> EvalResult:
        position = (float(obs.fields["lat"]), float(obs.fields["lon"]))
        inside = point_in_polygon(position, params.area)
        was_inside: bool | None = state.get("inside")

        entered = inside and (params.initial_as_enter if was_inside is None else not was_inside)
        return EvalResult(
            outcome=HIT if entered else MISS,
            extracted={"entered_at": {"lat": position[0], "lon": position[1]}} if entered else {},
            state_patch={"inside": inside},
        )
