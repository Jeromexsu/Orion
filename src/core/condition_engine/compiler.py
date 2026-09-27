from collections.abc import Mapping

from pydantic import ValidationError

from core.condition_engine.definitions import BranchDef, ConditionDef, LeafDef
from core.condition_engine.errors import ConditionCompileError, UnknownEvaluatorError
from core.condition_engine.registry import EvaluatorRegistry
from core.condition_engine.tree import BranchNode, ConditionNode, ConditionTree, LeafNode
from core.target import Observation

DeclaredObservables = Mapping[str, type[Observation]]
"""Observable target ID (e.g. "t1:position") -> the observation class it produces.

Carries two things: the keys are the scope a condition may refer to (the observable
targets the template declares), the values are the shape of each one's observations
(the fields an evaluator's requires is checked against). Assembled by the template
compiler from its observable declarations without creating any observable target.
"""


class ConditionCompiler:
    """把条件定义（ConditionDef）编译成 ConditionTree。

    输入必须是已解析好的静态定义；JSON → ConditionDef 属于边界（API 层 / 持久化层）的职责，
    由 Pydantic 完成。

    可用的可观测目标及其观测类由调用方传入（declared_observables），条件引擎不去查询 target 模块，
    字段由观测类自己描述。校验：判断方式存在、引用的可观测目标已声明、它的观测有判断方式需要的字段、判定标准合法。
    """

    def __init__(self, evaluator_registry: EvaluatorRegistry) -> None:
        self._evaluator_registry = evaluator_registry

    def compile(
        self, condition_def: ConditionDef, declared_observables: DeclaredObservables
    ) -> ConditionTree:
        """Compile and validate a whole condition into a ConditionTree.

        Closes the definition-time gap between a leaf, its evaluator and the observable
        target it refers to: the observable target must be declared, and the observation
        it produces must have every field the evaluator requires. Has no side effects.

        Args:
            condition_def: The parsed condition definition.
            declared_observables: The observable targets the condition may refer to, each
                with the observation class it produces; supplied by the caller (the
                template compiler) so the engine never queries the target module.

        Returns:
            The compiled tree.

        Raises:
            ConditionCompileError: With every error found, each prefixed by its node path
                (e.g. "root/1/0: ...").
        """
        errors: list[str] = []
        root = self._compile(condition_def, declared_observables, "root", errors)
        if errors or root is None:
            raise ConditionCompileError(errors)
        return ConditionTree(root)

    def _compile(
        self,
        condition_def: ConditionDef,
        declared_observables: DeclaredObservables,
        path: str,
        errors: list[str],
    ) -> ConditionNode | None:
        if isinstance(condition_def, BranchDef):
            return self._compile_branch(condition_def, declared_observables, path, errors)
        return self._compile_leaf(condition_def, declared_observables, path, errors)

    def _compile_branch(
        self,
        branch_def: BranchDef,
        declared_observables: DeclaredObservables,
        path: str,
        errors: list[str],
    ) -> ConditionNode | None:
        if branch_def.op == "not" and len(branch_def.children) != 1:
            errors.append(f"{path}: 'not' takes exactly one child, got {len(branch_def.children)}")
        elif not branch_def.children:
            errors.append(f"{path}: '{branch_def.op}' needs at least one child")

        children = [
            self._compile(child_def, declared_observables, f"{path}/{i}", errors)
            for i, child_def in enumerate(branch_def.children)
        ]
        compiled = [c for c in children if c is not None]
        if len(compiled) != len(children):
            return None
        return BranchNode(path, branch_def.op, compiled)

    def _compile_leaf(
        self,
        leaf_def: LeafDef,
        declared_observables: DeclaredObservables,
        path: str,
        errors: list[str],
    ) -> ConditionNode | None:
        """ Check and compile leaf condition definition into leaf condition node.

        Verify:
            1. declared evaluator exists
            2. declared observables are in range of observables declared in template
            3. fields of observation can satisfy requirements of evaluator
            4. criteria syntax ok
        
        Args:
            leaf_def: leaf condition definition
            declared_observables: declared observables in template and their observations' shapes
            path: path to reach this definition node from root
            errors: errors
        
        Returns:
            A leaf condition node if all test passed
        """

        # get evaluator instance declared in definition
        try:
            evaluator = self._evaluator_registry.get(leaf_def.op)
        except UnknownEvaluatorError:
            errors.append(f"{path}: unknown evaluator op {leaf_def.op!r}")
            return None

        ok = True
        # get observation shape of the mentioned observable
        observation_type = declared_observables.get(leaf_def.observable)
        if observation_type is None:
            errors.append(f"{path}: unknown observable {leaf_def.observable!r}")
            ok = False
        # check if fields of observation can satisfy requirements of evaluator
        else:
            missing = set(evaluator.requires) - set(observation_type.model_fields)
            if missing:
                errors.append(
                    f"{path}: observable {leaf_def.observable!r} lacks fields {sorted(missing)}"
                )
                ok = False
        # check syntax of criteria
        try:
            criteria = evaluator.criteria_model.model_validate(leaf_def.criteria)
        except ValidationError as e:
            errors.append(f"{path}: invalid criteria for {leaf_def.op!r}: {e}")
            return None

        return LeafNode(path, leaf_def.observable, evaluator, criteria) if ok else None
