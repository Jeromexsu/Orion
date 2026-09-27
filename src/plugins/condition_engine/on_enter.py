"""示例 Evaluator：进入区域。有状态的判断方式照这个写。"""

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field

from core.condition_engine import HIT, MISS, EvalResult, Evaluator
from core.target import ObservationEnvelope

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
    """模板里 LeafDef.params 的形状。"""

    area: Polygon = Field(min_length=3)
    initial_as_enter: bool = False   # 首次观测就在区域内是否算“进入”


class OnEnter(Evaluator[OnEnterParams]):
    """上一次在区域外、这一次在区域内 → 命中。状态里记住上一次是否在区域内。"""

    type = "onEnter"
    requires = frozenset({"lat", "lon"})
    params_model = OnEnterParams

    def evaluate(
        self, params: OnEnterParams, envelope: ObservationEnvelope, state: Mapping[str, Any]
    ) -> EvalResult:
        """命中时 extracted 带进入时的位置；每次都返回新的 inside 状态。"""
        observation = envelope.observation
        position = (float(getattr(observation, "lat")), float(getattr(observation, "lon")))
        inside = point_in_polygon(position, params.area)
        was_inside: bool | None = state.get("inside")

        entered = inside and (params.initial_as_enter if was_inside is None else not was_inside)
        return EvalResult(
            outcome=HIT if entered else MISS,
            extracted={"entered_at": {"lat": position[0], "lon": position[1]}} if entered else {},
            state_patch={"inside": inside},
        )
