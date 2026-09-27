from collections.abc import Mapping, Set

from pydantic import ValidationError

from core.condition_engine.definitions import ConditionDef, LeafDef, OpDef

FieldsByObservable = Mapping[str, Set[str]]
"""可观测目标 ID（如 "t1:position"）→ 它的观测有哪些字段（如 {"lat", "lon", "altitude_m"}）。"""
from core.condition_engine.errors import ConditionCompileError
from core.condition_engine.registry import EvaluatorRegistry
from core.condition_engine.tree import ConditionNode, ConditionTree, LeafNode, OpNode


class ConditionCompiler:
    """把条件定义（ConditionDef）编译成 ConditionTree。

    输入必须是已解析好的静态定义；JSON → ConditionDef 属于边界（API 层 / 持久化层）的职责，
    由 Pydantic 完成。

    可用的可观测目标及其字段由调用方传入（fields_by_observable），条件引擎不去查询 target 模块。
    校验：判断方式存在、引用的可观测目标在 fields_by_observable 里、它有判断方式需要的字段、参数合法。
    """

    def __init__(self, evaluator_registry: EvaluatorRegistry) -> None:
        self._evaluator_registry = evaluator_registry

    def compile(
        self, condition_def: ConditionDef, fields_by_observable: FieldsByObservable
    ) -> ConditionTree:
        """编译并校验整棵树，返回 ConditionTree。

        fields_by_observable：允许引用的可观测目标及其观测字段，由调用方（模板编译器）提供。
        所有错误收集后一次性抛 ConditionCompileError，每条带节点路径（如 "root/1/0: ..."）。无副作用。
        """
        errors: list[str] = []
        root = self._compile(condition_def, "root", fields_by_observable, errors)
        if errors or root is None:
            raise ConditionCompileError(errors)
        return ConditionTree(root)

    def _compile(
        self, node: ConditionDef, path: str, fields_by_observable: FieldsByObservable, errors: list[str]
    ) -> ConditionNode | None:
        if isinstance(node, OpDef):
            return self._compile_op(node, path, fields_by_observable, errors)
        return self._compile_leaf(node, path, fields_by_observable, errors)

    def _compile_op(
        self, node: OpDef, path: str, fields_by_observable: FieldsByObservable, errors: list[str]
    ) -> ConditionNode | None:
        if node.op == "not" and len(node.children) != 1:
            errors.append(f"{path}: 'not' takes exactly one child, got {len(node.children)}")
        elif not node.children:
            errors.append(f"{path}: '{node.op}' needs at least one child")

        children = [
            self._compile(c, f"{path}/{i}", fields_by_observable, errors)
            for i, c in enumerate(node.children)
        ]
        compiled = [c for c in children if c is not None]
        if len(compiled) != len(children):
            return None
        return OpNode(path, node.op, compiled)

    def _compile_leaf(
        self, node: LeafDef, path: str, fields_by_observable: FieldsByObservable, errors: list[str]
    ) -> ConditionNode | None:
        if not self._evaluator_registry.has(node.type):
            errors.append(f"{path}: unknown condition type {node.type!r}")
            return None
        evaluator = self._evaluator_registry.get(node.type)

        ok = True
        available = fields_by_observable.get(node.observable)
        if available is None:
            errors.append(f"{path}: unknown observable {node.observable!r}")
            ok = False
        else:
            missing = set(evaluator.requires) - set(available)
            if missing:
                errors.append(
                    f"{path}: observable {node.observable!r} lacks fields {sorted(missing)}"
                )
                ok = False

        try:
            params = evaluator.params_model.model_validate(node.params)
        except ValidationError as e:
            errors.append(f"{path}: invalid params for {node.type!r}: {e}")
            return None

        return LeafNode(path, node.observable, evaluator, params) if ok else None
