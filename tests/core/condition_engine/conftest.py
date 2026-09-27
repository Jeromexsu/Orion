from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from itertools import count
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, TypeAdapter

from core.condition_engine import (
    HIT,
    MISS,
    NOT_APPLICABLE,
    ConditionCompiler,
    ConditionDef,
    ConditionTree,
    EvalResult,
    Evaluator,
    EvaluatorRegistry,
    evaluator,
)
from core.observation import Observation, ObservationEnvelope
from plugins.condition_engine.on_enter import OnEnter
from plugins.observed_points.position import PositionObservation

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
    """测试辅助：构造一条观测外壳。at 是相对 T0 的小时数；观测类按可观测目标声明取（未声明的用 AnyObservation）。"""
    observation_class = DECLARED_OBSERVABLES.get(observable_id, AnyObservation)
    return ObservationEnvelope(
        observable_id=observable_id,
        upstream="test",
        observation=observation_class(**fields),
        occurred_at=T0 + timedelta(hours=at),
        source_id=f"test#{next(_seq)}",
    )


class GtCriteria(BaseModel):
    field: str
    value: float


class WithAltitude(PositionObservation):
    """位置 + 一个可为空的高度。"""

    alt: float | None = None


@evaluator()
class Gt(Evaluator[GtCriteria, WithAltitude]):
    """无状态测试用判断：alt > value。高度为空时不适用——可为空的字段由判断方式自己处理。"""

    def evaluate(
        self,
        observation: WithAltitude,
        occurred_at: datetime,
        state: Mapping[str, Any],
        criteria: GtCriteria,
    ) -> EvalResult:
        if observation.alt is None:
            return EvalResult(outcome=NOT_APPLICABLE)
        hit = observation.alt > criteria.value
        return EvalResult(outcome=HIT if hit else MISS, extracted={"alt": observation.alt} if hit else {})


# 可引用的可观测目标及其观测类：t1:position 有高度；t2:position 只是位置
DECLARED_OBSERVABLES: dict[str, type[Observation]] = {
    "t1:position": WithAltitude,
    "t2:position": PositionObservation,
}


SQUARE = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)]


@pytest.fixture
def compiler() -> ConditionCompiler:
    registry = EvaluatorRegistry()
    registry.register(OnEnter())
    registry.register(Gt())
    return ConditionCompiler(registry)
