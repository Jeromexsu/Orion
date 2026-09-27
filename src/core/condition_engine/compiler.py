from collections.abc import Mapping

from pydantic import ValidationError

from core.condition_engine.definitions import BranchDef, ConditionDef, LeafDef
from core.condition_engine.errors import ConditionCompileError
from core.condition_engine.registry import EvaluatorRegistry
from core.condition_engine.tree import BranchNode, ConditionNode, ConditionTree, LeafNode
from core.target import Observation

ObservationTypes = Mapping[str, type[Observation]]
"""可观测目标 ID（如 "t1:position"）→ 它产出的观测类（如 PositionObservation）。"""


class ConditionCompiler:
    """把条件定义（ConditionDef）编译成 ConditionTree。

    输入必须是已解析好的静态定义；JSON → ConditionDef 属于边界（API 层 / 持久化层）的职责，
    由 Pydantic 完成。

    可用的可观测目标及其观测类由调用方传入（observation_types），条件引擎不去查询 target 模块，
    字段由观测类自己描述。校验：判断方式存在、引用的可观测目标已声明、它的观测有判断方式需要的字段、判定标准合法。
    """

    def __init__(self, evaluator_registry: EvaluatorRegistry) -> None:
        self._evaluator_registry = evaluator_registry

    def compile(
        self, condition_def: ConditionDef, observation_types: ObservationTypes
    ) -> ConditionTree:
        """Compile and validate a whole condition into a ConditionTree.

        Closes the definition-time gap between a leaf, its evaluator and the observable
        target it refers to: the observable target must be declared, and the observation
        it produces must have every field the evaluator requires. Has no side effects.

        Args:
            condition_def: The parsed condition definition.
            observation_types: The observable targets the condition may refer to, each
                with the observation class it produces; supplied by the caller (the
                template compiler) so the engine never queries the target module.

        Returns:
            The compiled tree.

        Raises:
            ConditionCompileError: With every error found, each prefixed by its node path
                (e.g. "root/1/0: ...").
        """
        errors: list[str] = []
        root = self._compile(condition_def, "root", observation_types, errors)
        if errors or root is None:
            raise ConditionCompileError(errors)
        return ConditionTree(root)

    def _compile(
        self, node: ConditionDef, path: str, observation_types: ObservationTypes, errors: list[str]
    ) -> ConditionNode | None:
        if isinstance(node, BranchDef):
            return self._compile_op(node, path, observation_types, errors)
        return self._compile_leaf(node, path, observation_types, errors)

    def _compile_op(
        self, node: BranchDef, path: str, observation_types: ObservationTypes, errors: list[str]
    ) -> ConditionNode | None:
        if node.op == "not" and len(node.children) != 1:
            errors.append(f"{path}: 'not' takes exactly one child, got {len(node.children)}")
        elif not node.children:
            errors.append(f"{path}: '{node.op}' needs at least one child")

        children = [
            self._compile(c, f"{path}/{i}", observation_types, errors)
            for i, c in enumerate(node.children)
        ]
        compiled = [c for c in children if c is not None]
        if len(compiled) != len(children):
            return None
        return BranchNode(path, node.op, compiled)

    def _compile_leaf(
        self, node: LeafDef, path: str, observation_types: ObservationTypes, errors: list[str]
    ) -> ConditionNode | None:
        if not self._evaluator_registry.has(node.op):
            errors.append(f"{path}: unknown evaluator op {node.op!r}")
            return None
        evaluator = self._evaluator_registry.get(node.op)

        ok = True
        observation_type = observation_types.get(node.observable)
        if observation_type is None:
            errors.append(f"{path}: unknown observable {node.observable!r}")
            ok = False
        else:
            missing = set(evaluator.requires) - set(observation_type.model_fields)
            if missing:
                errors.append(
                    f"{path}: observable {node.observable!r} lacks fields {sorted(missing)}"
                )
                ok = False

        try:
            criteria = evaluator.criteria_model.model_validate(node.criteria)
        except ValidationError as e:
            errors.append(f"{path}: invalid criteria for {node.op!r}: {e}")
            return None

        return LeafNode(path, node.observable, evaluator, criteria) if ok else None
