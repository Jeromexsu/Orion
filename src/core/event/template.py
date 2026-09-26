from collections.abc import Set

from core.condition_engine import ConditionCompileError, ConditionEngine, ConditionTree
from core.contracts import ConditionDef, MountPoint
from core.event.definitions import ObservationDef, OperatorMount, TemplateDef
from core.event.errors import TemplateCompileError, TemplateScopeError
from core.operators import OperatorError, OperatorRegistry


class CompiledRule:
    def __init__(self, name: str, tree: ConditionTree, hooks: tuple[OperatorMount, ...]) -> None:
        self.name = name
        self.tree = tree
        self.hooks = hooks


class SubEventTemplate:
    """编译好的模板：不可变、带版本，持有开启条件树和每条规则的条件树。只通过 compile 构造。"""

    def __init__(
        self,
        definition: TemplateDef,
        open_tree: ConditionTree,
        rules: tuple[CompiledRule, ...],
        hooks: tuple[OperatorMount, ...],
    ) -> None:
        self._definition = definition
        self._open_tree = open_tree
        self._rules = rules
        self._hooks = hooks

    @classmethod
    def compile(
        cls, definition: TemplateDef, conditions: ConditionEngine, operators: OperatorRegistry
    ) -> "SubEventTemplate":
        errors: list[str] = []
        rules: list[CompiledRule] = []

        declared = [o.observable_id for o in definition.observations]
        dupes = sorted({o for o in declared if declared.count(o) > 1})
        if dupes:
            errors.append(f"duplicate observations {dupes}")

        def compile_tree(where: str, condition: ConditionDef) -> ConditionTree | None:
            try:
                tree = conditions.compile(condition)
            except ConditionCompileError as e:
                errors.extend(f"{where}: {msg}" for msg in e.errors)
                return None
            undeclared = tree.targets() - set(declared)
            if undeclared:
                errors.append(f"{where}: targets {sorted(undeclared)} not in observations")
            return tree

        open_tree = compile_tree("open_condition", definition.open_condition)

        names = [r.name for r in definition.rules]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            errors.append(f"duplicate rule names {dupes}")

        for rule in definition.rules:
            tree = compile_tree(f"rule {rule.name!r}", rule.condition)
            hooks: list[OperatorMount] = []
            for i, mount in enumerate(rule.hooks):
                where = f"rule {rule.name!r} hook {i}"
                if mount.mount_point != "rule_hit":
                    errors.append(f"{where}: rule hooks must mount at 'rule_hit'")
                    continue
                bound = _bind(mount, operators, where, errors)
                if bound is not None:
                    hooks.append(bound)
            if tree is not None:
                rules.append(CompiledRule(rule.name, tree, tuple(hooks)))

        template_hooks: list[OperatorMount] = []
        for i, mount in enumerate(definition.hooks):
            where = f"hook {i}"
            if mount.mount_point == "rule_hit":
                errors.append(f"{where}: 'rule_hit' hooks belong on a rule")
                continue
            bound = _bind(mount, operators, where, errors)
            if bound is not None:
                template_hooks.append(bound)

        if errors or open_tree is None:
            raise TemplateCompileError(errors)
        return cls(definition, open_tree, tuple(rules), tuple(template_hooks))

    @property
    def definition(self) -> TemplateDef:
        return self._definition

    @property
    def id(self) -> str:
        return self._definition.id

    @property
    def version(self) -> int:
        return self._definition.version

    @property
    def observations(self) -> tuple[ObservationDef, ...]:
        return tuple(self._definition.observations)

    @property
    def open_tree(self) -> ConditionTree:
        return self._open_tree

    @property
    def rules(self) -> tuple[CompiledRule, ...]:
        return self._rules

    @property
    def target_ids(self) -> frozenset[str]:
        """观测声明里的静态目标 ID。"""
        return frozenset(o.target_id for o in self._definition.observations)

    def hooks_at(self, mount_point: MountPoint) -> tuple[OperatorMount, ...]:
        return tuple(h for h in self._hooks if h.mount_point == mount_point)

    def validate(self, namespace: Set[str]) -> None:
        """跨对象约束：观测的目标必须都在父事件的目标命名空间里。"""
        missing = self.target_ids - namespace
        if missing:
            raise TemplateScopeError(
                f"template {self.id} v{self.version} observes targets outside the namespace: "
                f"{sorted(missing)}"
            )


def _bind(
    mount: OperatorMount, operators: OperatorRegistry, where: str, errors: list[str]
) -> OperatorMount | None:
    """校验算子挂载，返回参数规范化后的挂载。"""
    try:
        params = operators.validate_mount(mount.operator, "instance", mount.mount_point, mount.params)
    except OperatorError as e:
        errors.append(f"{where}: {e}")
        return None
    return mount.model_copy(update={"params": params.model_dump()})
