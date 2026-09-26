from collections.abc import Mapping
from typing import Any

from pydantic import TypeAdapter, ValidationError

from core.contracts import ConditionDef, LeafDef, OpDef
from core.condition_engine.errors import ConditionCompileError
from core.condition_engine.registry import EvaluatorRegistry
from core.condition_engine.resolver import TargetResolver
from core.condition_engine.tree import ConditionNode, ConditionTree, LeafNode, OpNode

_condition_adapter: TypeAdapter[LeafDef | OpDef] = TypeAdapter(ConditionDef)


class ConditionEngine:
    """把条件定义编译成 ConditionTree。

    只做条件自身的合法性校验（判断方式存在、目标存在且有需要的字段、参数合法）；
    “目标是否在模板允许范围内”由 SubEventTemplate.validate() 负责。
    """

    def __init__(self, evaluators: EvaluatorRegistry, resolver: TargetResolver) -> None:
        self._evaluators = evaluators
        self._resolver = resolver

    @staticmethod
    def parse(raw: Mapping[str, Any]) -> LeafDef | OpDef:
        """结构校验：JSON → ConditionDef。失败抛 pydantic.ValidationError。"""
        return _condition_adapter.validate_python(raw)

    def compile(self, definition: LeafDef | OpDef | Mapping[str, Any]) -> ConditionTree:
        if not isinstance(definition, LeafDef | OpDef):
            definition = self.parse(definition)
        errors: list[str] = []
        root = self._compile(definition, "root", errors)
        if errors or root is None:
            raise ConditionCompileError(errors)
        return ConditionTree(root)

    def _compile(self, node: LeafDef | OpDef, path: str, errors: list[str]) -> ConditionNode | None:
        if isinstance(node, OpDef):
            return self._compile_op(node, path, errors)
        return self._compile_leaf(node, path, errors)

    def _compile_op(self, node: OpDef, path: str, errors: list[str]) -> ConditionNode | None:
        if node.op == "not" and len(node.children) != 1:
            errors.append(f"{path}: 'not' takes exactly one child, got {len(node.children)}")
        elif not node.children:
            errors.append(f"{path}: '{node.op}' needs at least one child")

        children = [self._compile(c, f"{path}/{i}", errors) for i, c in enumerate(node.children)]
        compiled = [c for c in children if c is not None]
        if len(compiled) != len(children):
            return None
        return OpNode(path, node.op, compiled)

    def _compile_leaf(self, node: LeafDef, path: str, errors: list[str]) -> ConditionNode | None:
        if not self._evaluators.has(node.type):
            errors.append(f"{path}: unknown condition type {node.type!r}")
            return None
        evaluator = self._evaluators.get(node.type)

        ok = True
        schema = self._resolver.dynamic_schema(node.target)
        if schema is None:
            errors.append(f"{path}: unknown target {node.target!r}")
            ok = False
        else:
            missing = set(evaluator.requires) - set(schema.model_fields)
            if missing:
                errors.append(f"{path}: target {node.target!r} lacks fields {sorted(missing)}")
                ok = False

        try:
            params = evaluator.params_model.model_validate(node.params)
        except ValidationError as e:
            errors.append(f"{path}: invalid params for {node.type!r}: {e}")
            return None

        return LeafNode(path, node.target, evaluator, params) if ok else None
