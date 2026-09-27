from abc import ABC, abstractmethod
from collections.abc import Mapping, Set
from types import MappingProxyType
from typing import Any, Literal

from pydantic import BaseModel

from core.condition_engine.evaluator import (
    HIT,
    MISS,
    NOT_APPLICABLE,
    EvalResult,
    Evaluator,
    Outcome,
)
from core.target import ObservationEnvelope

TreeState = Mapping[str, Mapping[str, Any]]
"""整棵树的状态：叶子路径（如 "root/1"）→ 该叶子的状态。"""

_Changes = dict[str, dict[str, Any]]
"""树内部传递：本次状态变了的叶子路径 → 该叶子的新状态。"""


class ConditionNode(ABC):
    """条件树节点。path 是它在树里的位置（如 "root/1/0"），用作状态的键和报错定位。"""

    def __init__(self, path: str) -> None:
        self.path = path

    @abstractmethod
    def evaluate(
        self, envelope: ObservationEnvelope, state: TreeState
    ) -> tuple[EvalResult, _Changes]:
        """Evaluate one observation against this node and its subtree.

        Args:
            envelope: The observation to evaluate.
            state: State of the whole tree; not modified.

        Returns:
            The result (its state is always None at node level) and the new states
            of the leaves in this subtree whose state changed.
        """
        ...


class LeafNode(ConditionNode):
    """叶子：一个可观测目标 + 一种判断方式 + 已解析的参数。

    观测不属于这个可观测目标，或缺少判断方式需要的字段时，返回“不适用”，不调用判断方式。
    """

    def __init__(
        self, path: str, observable: str, evaluator: Evaluator[Any], params: BaseModel
    ) -> None:
        super().__init__(path)
        self.observable = observable
        self.evaluator = evaluator
        self.params = params

    def evaluate(
        self, envelope: ObservationEnvelope, state: TreeState
    ) -> tuple[EvalResult, _Changes]:
        requires: Set[str] = self.evaluator.requires
        observation = envelope.observation
        if envelope.observable_id != self.observable or any(
            getattr(observation, f, None) is None for f in requires
        ):
            # 不是这个叶子的可观测目标，或需要的字段缺失 / 为空（如没有高度的观测）
            return EvalResult(outcome=NOT_APPLICABLE), {}

        old_state = dict(state.get(self.path, {}))
        leaf_state = MappingProxyType(dict(old_state))
        # 每个叶子拿一份副本：判断方式即使修改了也影响不到其他叶子和调用方
        result = self.evaluator.evaluate(self.params, envelope.model_copy(deep=True), leaf_state)

        entry: dict[str, Any] = {
            "path": self.path,
            "type": self.evaluator.type,
            "observable": self.observable,
            "outcome": result.outcome,
            "occurred_at": envelope.occurred_at.isoformat(),
            "fields": {f: getattr(observation, f) for f in sorted(requires)},
        }
        # 判断方式返回的是本叶子的新状态；“不适用”不得改状态，和旧状态相同也不算变
        changes: _Changes = (
            {self.path: dict(result.state)}
            if result.outcome != NOT_APPLICABLE
            and result.state is not None
            and result.state != old_state
            else {}
        )
        return result.model_copy(update={"trace": [entry, *result.trace], "state": None}), changes


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

    def evaluate(
        self, envelope: ObservationEnvelope, state: TreeState
    ) -> tuple[EvalResult, _Changes]:
        evaluated = [child.evaluate(envelope, state) for child in self.children]
        results = [r for r, _ in evaluated]

        changes: _Changes = {}
        trace: list[dict[str, Any]] = []
        for r, child_changes in evaluated:
            changes.update(child_changes)
            trace.extend(r.trace)

        outcome, confidence, extracted = self._combine(results)
        result = EvalResult(
            outcome=outcome, confidence=confidence, extracted=extracted, trace=trace
        )
        return result, changes

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


class ConditionTree:
    """编译好的条件树。只通过 ConditionCompiler.compile 构造。"""

    def __init__(self, root: ConditionNode) -> None:
        self._root = root

    def evaluate(self, envelope: ObservationEnvelope, state: TreeState) -> EvalResult:
        """Evaluate one observation against the whole tree.

        Pure: the given state is not modified. The caller owns the state (the tree is
        shared by every event of a template version), keeps the returned new state and
        persists it when it changed.

        Args:
            envelope: The observation to evaluate.
            state: State of the whole tree as last returned (empty on first call).

        Returns:
            The result. Its state is the whole new tree state, or None if no leaf's
            state changed.
        """
        result, changes = self._root.evaluate(envelope, state)
        if not changes:
            return result
        new_state = {path: dict(leaf) for path, leaf in state.items()}
        new_state.update(changes)
        return result.model_copy(update={"state": new_state})
