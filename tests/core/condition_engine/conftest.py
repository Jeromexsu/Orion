from collections.abc import Mapping
from typing import Any

import pytest
from pydantic import BaseModel

from core.condition_engine import ConditionEngine, EvaluatorRegistry, LeafEvaluator
from core.contracts import HIT, MISS, EvalResult
from plugins.condition_engine.on_enter import OnEnter


class Obs:
    """满足 Observation 的最小实现。"""

    def __init__(self, observable_id: str, **fields: Any) -> None:
        self.observable_id = observable_id
        self.fields: dict[str, Any] = fields


class GtParams(BaseModel):
    field: str
    value: float


class Gt(LeafEvaluator[GtParams]):
    """无状态测试用判断：fields[field] > value。"""

    type = "gt"
    requires = frozenset({"alt"})
    params_model = GtParams

    def evaluate(
        self, params: GtParams, fields: Mapping[str, Any], state: Mapping[str, Any]
    ) -> EvalResult:
        hit = fields[params.field] > params.value
        return EvalResult(outcome=HIT if hit else MISS, extracted={"alt": fields["alt"]} if hit else {})


class StaticResolver:
    """t1:position 有 lat/lon/alt；t2:position 只有 lat/lon。"""

    def __init__(self) -> None:
        class Full(BaseModel):
            lat: float
            lon: float
            alt: float

        class Flat(BaseModel):
            lat: float
            lon: float

        self.schemas: dict[str, type[BaseModel]] = {"t1:position": Full, "t2:position": Flat}

    def dynamic_schema(self, observable_id: str) -> type[BaseModel] | None:
        return self.schemas.get(observable_id)


SQUARE = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)]


@pytest.fixture
def engine() -> ConditionEngine:
    registry = EvaluatorRegistry()
    registry.register(OnEnter())
    registry.register(Gt())
    return ConditionEngine(registry, StaticResolver())
