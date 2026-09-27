from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from itertools import count
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, TypeAdapter

from core.condition_engine import (
    HIT,
    MISS,
    ConditionCompiler,
    ConditionDef,
    ConditionTree,
    EvalResult,
    Evaluator,
    EvaluatorRegistry,
    evaluator,
)
from core.target import Observation, ObservationEnvelope
from plugins.condition_engine.on_enter import OnEnter

_condition_def: TypeAdapter[ConditionDef] = TypeAdapter(ConditionDef)


def parse(raw: dict[str, Any]) -> ConditionDef:
    """测试辅助：dict → ConditionDef（生产代码里这一步在 API / 持久化边界完成）。"""
    return _condition_def.validate_python(raw)


def compile_(
    compiler: ConditionCompiler,
    raw: dict[str, Any],
    declared_observables: dict[str, type[Observation]] | None = None,
) -> ConditionTree:
    return compiler.compile(
        parse(raw), DECLARED_OBSERVABLES if declared_observables is None else declared_observables
    )


T0 = datetime(2026, 9, 26, tzinfo=UTC)


_seq = count()


class AnyObservation(Observation):
    """测试用观测：允许任意字段，便于直接写 lat=..., alt=...。"""

    model_config = ConfigDict(frozen=True, extra="allow")


def make_envelope(observable_id: str, at: float = 0, **fields: Any) -> ObservationEnvelope:
    """测试辅助：构造一条观测外壳。at 是相对 T0 的小时数。"""
    return ObservationEnvelope(
        observable_id=observable_id,
        upstream="test",
        observation=AnyObservation(**fields),
        occurred_at=T0 + timedelta(hours=at),
        source_id=f"test#{next(_seq)}",
    )


class GtCriteria(BaseModel):
    field: str
    value: float


@evaluator(requires={"alt"})
class Gt(Evaluator[GtCriteria]):
    """无状态测试用判断：fields[field] > value。"""


    def evaluate(
        self,
    observation: Observation,
    occurred_at: datetime,
    state: Mapping[str, Any],
    criteria: GtCriteria,
) -> EvalResult:
        value = getattr(observation, criteria.field)
        hit = value > criteria.value
        return EvalResult(outcome=HIT if hit else MISS, extracted={"alt": value} if hit else {})


class WithAltitude(Observation):
    lat: float
    lon: float
    alt: float | None = None


class WithoutAltitude(Observation):
    lat: float
    lon: float


# 可引用的可观测目标及其观测类：t1:position 有 lat/lon/alt；t2:position 只有 lat/lon
DECLARED_OBSERVABLES: dict[str, type[Observation]] = {
    "t1:position": WithAltitude,
    "t2:position": WithoutAltitude,
}


SQUARE = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)]


@pytest.fixture
def compiler() -> ConditionCompiler:
    registry = EvaluatorRegistry()
    registry.register(OnEnter())
    registry.register(Gt())
    return ConditionCompiler(registry)
