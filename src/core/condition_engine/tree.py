from abc import ABC, abstractmethod
from collections.abc import Mapping, Set
from datetime import datetime
from types import MappingProxyType
from typing import Any, Literal

from pydantic import BaseModel

from core.condition_engine.evaluator import Evaluator
from core.condition_engine.observation import Observation
from core.condition_engine.result import HIT, MISS, NOT_APPLICABLE, EvalResult, Outcome


class _ReadOnlyObservation:
    """交给判断方式的只读观测：fields 是只读视图，判断方式改不动原数据。"""

    def __init__(self, observation: Observation) -> None:
        self._observable_id = observation.observable_id
        self._fields = MappingProxyType(dict(observation.fields))
        self._occurred_at = observation.occurred_at

    @property
    def observable_id(self) -> str:
        return self._observable_id

    @property
    def fields(self) -> Mapping[str, Any]:
        return self._fields

    @property
    def occurred_at(self) -> datetime:
        return self._occurred_at

# 整棵树的状态：节点路径 → 该叶子的状态
TreeState = Mapping[str, Mapping[str, Any]]


def apply_state_patch(state: TreeState, patch: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """把 EvalResult.state_patch 合并进树状态，返回新 dict（不改入参）。"""
    merged = {path: dict(leaf) for path, leaf in state.items()}
    for path, leaf_patch in patch.items():
        merged.setdefault(path, {}).update(leaf_patch)
    return merged


class ConditionNode(ABC):
    def __init__(self, path: str) -> None:
        self.path = path

    @abstractmethod
    def evaluate(self, observation: Observation, state: TreeState) -> EvalResult: ...

    @abstractmethod
    def targets(self) -> frozenset[str]: ...


class LeafNode(ConditionNode):
    def __init__(
        self, path: str, target: str, evaluator: Evaluator[Any], params: BaseModel
    ) -> None:
        super().__init__(path)
        self.target = target
        self.evaluator = evaluator
        self.params = params

    def evaluate(self, observation: Observation, state: TreeState) -> EvalResult:
        requires: Set[str] = self.evaluator.requires
        if observation.observable_id != self.target or not requires <= observation.fields.keys():
            return EvalResult(outcome=NOT_APPLICABLE)

        leaf_state = MappingProxyType(dict(state.get(self.path, {})))
        result = self.evaluator.evaluate(self.params, _ReadOnlyObservation(observation), leaf_state)

        entry: dict[str, Any] = {
            "path": self.path,
            "type": self.evaluator.type,
            "target": self.target,
            "outcome": result.outcome,
            "occurred_at": observation.occurred_at.isoformat(),
            "fields": {k: observation.fields[k] for k in sorted(requires)},
        }
        patch = (
            {self.path: result.state_patch}
            if result.outcome != NOT_APPLICABLE and result.state_patch
            else {}
        )
        return result.model_copy(update={"trace": [entry, *result.trace], "state_patch": patch})

    def targets(self) -> frozenset[str]:
        return frozenset({self.target})


class OpNode(ConditionNode):
    """组合节点。永远不短路：每次都评估所有子节点，保证有状态的叶子不漏更新。

    三值逻辑，“不适用”视为中性：
    - all：有未命中 → 未命中；全不适用 → 不适用；否则命中
    - any：有命中 → 命中；全不适用 → 不适用；否则未命中
    - not：命中 ↔ 未命中，不适用保持不适用
    """

    def __init__(
        self, path: str, op: Literal["all", "any", "not"], children: list[ConditionNode]
    ) -> None:
        super().__init__(path)
        self.op = op
        self.children = children

    def evaluate(self, observation: Observation, state: TreeState) -> EvalResult:
        results = [child.evaluate(observation, state) for child in self.children]

        patch: dict[str, Any] = {}
        trace: list[dict[str, Any]] = []
        for r in results:
            patch.update(r.state_patch)
            trace.extend(r.trace)

        outcome, confidence, extracted = self._combine(results)
        return EvalResult(
            outcome=outcome,
            confidence=confidence,
            extracted=extracted,
            trace=trace,
            state_patch=patch,
        )

    def _combine(self, results: list[EvalResult]) -> tuple[Outcome, float, dict[str, Any]]:
        applicable = [r for r in results if r.outcome != NOT_APPLICABLE]
        hits = [r for r in applicable if r.outcome == HIT]
        misses = [r for r in applicable if r.outcome == MISS]

        if self.op == "not":
            r = results[0]
            if r.outcome == NOT_APPLICABLE:
                return NOT_APPLICABLE, 1.0, {}
            return (MISS if r.outcome == HIT else HIT), r.confidence, {}

        if not applicable:
            return NOT_APPLICABLE, 1.0, {}

        extracted: dict[str, Any] = {}
        for r in hits:
            extracted.update(r.extracted)

        if self.op == "all":
            if misses:
                return MISS, max(r.confidence for r in misses), {}
            return HIT, min(r.confidence for r in hits), extracted

        # any
        if hits:
            return HIT, max(r.confidence for r in hits), extracted
        return MISS, min(r.confidence for r in misses), {}

    def targets(self) -> frozenset[str]:
        return frozenset[str]().union(*(c.targets() for c in self.children))


class ConditionTree:
    """编译好的条件树。只通过 ConditionEngine.compile 构造。"""

    def __init__(self, root: ConditionNode) -> None:
        self._root = root

    def evaluate(self, observation: Observation, state: TreeState) -> EvalResult:
        """纯函数：不改 state；新状态在结果的 state_patch 里，用 apply_state_patch 合并。"""
        return self._root.evaluate(observation, state)

    def targets(self) -> frozenset[str]:
        """树里引用的全部 ObservableTarget ID，供 EventTemplate.validate 做范围检查。"""
        return self._root.targets()
