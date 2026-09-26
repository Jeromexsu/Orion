from pydantic import ValidationError

from core.condition_engine.errors import ConditionCompileError
from core.condition_engine.registry import EvaluatorRegistry
from core.condition_engine.resolver import TargetResolver
from core.condition_engine.tree import ConditionNode, ConditionTree, LeafNode, OpNode
from core.contracts import ConditionDef, LeafDef, OpDef


class ConditionEngine:
    """把条件定义（ConditionDef）编译成 ConditionTree。

    输入必须是已解析好的静态定义；JSON → ConditionDef 属于边界（API 层 / 持久化层）的职责，
    由 Pydantic 完成。这里只做条件自身的合法性校验：判断方式存在、目标存在且有需要的字段、参数合法。
    「引用的目标是否在允许范围内」由调用方负责（EventTemplate.compile 检查都在观测声明里）。
    """

    def __init__(self, evaluators: EvaluatorRegistry, resolver: TargetResolver) -> None:
        self._evaluators = evaluators
        self._resolver = resolver

    def compile(self, definition: ConditionDef) -> ConditionTree:
        errors: list[str] = []
        root = self._compile(definition, "root", errors)
        if errors or root is None:
            raise ConditionCompileError(errors)
        return ConditionTree(root)

    def _compile(self, node: ConditionDef, path: str, errors: list[str]) -> ConditionNode | None:
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
