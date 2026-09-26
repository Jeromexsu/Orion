from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import BaseModel, TypeAdapter

from core.condition_engine import (
    HIT,
    MISS,
    ConditionDef,
    ConditionEngine,
    ConditionTree,
    EvalResult,
    Evaluator,
    EvaluatorRegistry,
    Observation,
)
from plugins.condition_engine.on_enter import OnEnter

_condition_def: TypeAdapter[ConditionDef] = TypeAdapter(ConditionDef)


def parse(raw: dict[str, Any]) -> ConditionDef:
    """测试辅助：dict → ConditionDef（生产代码里这一步在 API / 持久化边界完成）。"""
    return _condition_def.validate_python(raw)


def compile_(
    engine: ConditionEngine, raw: dict[str, Any], fields: dict[str, set[str]] | None = None
) -> ConditionTree:
    return engine.compile(parse(raw), FIELDS if fields is None else fields)


T0 = datetime(2026, 9, 26, tzinfo=UTC)


class Obs:
    """满足 Observation 的最小实现。at 是相对 T0 的小时数。"""

    def __init__(self, observable_id: str, at: float = 0, **fields: Any) -> None:
        self.observable_id = observable_id
        self.fields: dict[str, Any] = fields
        self.occurred_at = T0 + timedelta(hours=at)


class GtParams(BaseModel):
    field: str
    value: float


class Gt(Evaluator[GtParams]):
    """无状态测试用判断：fields[field] > value。"""

    type = "gt"
    requires = frozenset({"alt"})
    params_model = GtParams

    def evaluate(self, params: GtParams, obs: Observation, state: Mapping[str, Any]) -> EvalResult:
        hit = obs.fields[params.field] > params.value
        return EvalResult(
            outcome=HIT if hit else MISS, extracted={"alt": obs.fields["alt"]} if hit else {}
        )


# 可用目标及其字段：t1:position 有 lat/lon/alt；t2:position 只有 lat/lon
FIELDS: dict[str, set[str]] = {"t1:position": {"lat", "lon", "alt"}, "t2:position": {"lat", "lon"}}


SQUARE = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)]


@pytest.fixture
def engine() -> ConditionEngine:
    registry = EvaluatorRegistry()
    registry.register(OnEnter())
    registry.register(Gt())
    return ConditionEngine(registry)
