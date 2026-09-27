from collections.abc import Set

from core.condition_engine import (
    ConditionCompileError,
    ConditionDef,
    ConditionEngine,
    ConditionTree,
)
from core.event.definitions import ObservationDef, OperatorMountDef, TemplateDef
from core.event.errors import TemplateCompileError, TemplateScopeError
from core.operators import MountPoint, OperatorError, OperatorRegistry
from core.target import TargetError, TargetManager


class CompiledRule:
    def __init__(
        self, name: str, tree: ConditionTree, hook_defs: tuple[OperatorMountDef, ...]
    ) -> None:
        self.name = name
        self.tree = tree
        self.hook_defs = hook_defs


class EventTemplate:
    """编译好的模板：不可变、带版本，持有开启条件树和每条规则的条件树。只通过 compile 构造。"""

    def __init__(
        self,
        template_def: TemplateDef,
        open_tree: ConditionTree,
        rules: tuple[CompiledRule, ...],
        hooks: tuple[OperatorMountDef, ...],
    ) -> None:
        self._template_def = template_def
        self._open_tree = open_tree
        self._rules = rules
        self._hooks = hooks

    @classmethod
    def compile(
        cls,
        template_def: TemplateDef,
        conditions: ConditionEngine,
        operator_registry: OperatorRegistry,
        targets: TargetManager,
    ) -> "EventTemplate":
        """编译并校验整个模板，所有错误一次收集进 TemplateCompileError。

        观测声明按 TargetManager 解析：目标与观察点存在、上游可用；观察点返回的观测有哪些字段，交给条件引擎，
        因此条件只能引用已声明的观测，且判断方式需要的字段必须存在。
        """
        errors: list[str] = []
        rules: list[CompiledRule] = []

        fields_by_observable: dict[str, set[str]] = {}
        for o in template_def.observation_defs:
            where = f"observation_def {o.observable_id!r}"
            if o.observable_id in fields_by_observable:
                errors.append(f"{where}: duplicate")
                continue
            try:
                observable = targets.get_observable(o.target_id, o.observed_point)
            except TargetError as e:
                errors.append(f"{where}: {e}")
                continue
            unavailable = sorted(set(o.upstreams) - set(observable.upstreams))
            if unavailable:
                errors.append(
                    f"{where}: upstreams {unavailable} not in available {list(observable.upstreams)}"
                )
            fields_by_observable[observable.id] = set(observable.observed_point.observation.model_fields)

        def compile_tree(where: str, condition_def: ConditionDef) -> ConditionTree | None:
            try:
                return conditions.compile(condition_def, fields_by_observable)
            except ConditionCompileError as e:
                errors.extend(f"{where}: {msg}" for msg in e.errors)
                return None

        open_tree = compile_tree("open_condition_def", template_def.open_condition_def)

        names = [r.name for r in template_def.rule_defs]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            errors.append(f"duplicate rule names {dupes}")

        for rule in template_def.rule_defs:
            tree = compile_tree(f"rule {rule.name!r}", rule.condition_def)
            hooks: list[OperatorMountDef] = []
            for i, mount in enumerate(rule.hook_defs):
                where = f"rule {rule.name!r} hook {i}"
                if mount.mount_point != "rule_hit":
                    errors.append(f"{where}: rule hooks must mount at 'rule_hit'")
                    continue
                bound = _bind(mount, operator_registry, where, errors)
                if bound is not None:
                    hooks.append(bound)
            if tree is not None:
                rules.append(CompiledRule(rule.name, tree, tuple(hooks)))

        template_hooks: list[OperatorMountDef] = []
        for i, mount in enumerate(template_def.hook_defs):
            where = f"hook {i}"
            if mount.mount_point == "rule_hit":
                errors.append(f"{where}: 'rule_hit' hooks belong on a rule")
                continue
            bound = _bind(mount, operator_registry, where, errors)
            if bound is not None:
                template_hooks.append(bound)

        if errors or open_tree is None:
            raise TemplateCompileError(errors)
        return cls(template_def, open_tree, tuple(rules), tuple(template_hooks))

    @property
    def template_def(self) -> TemplateDef:
        return self._template_def

    @property
    def id(self) -> str:
        return self._template_def.id

    @property
    def version(self) -> int:
        return self._template_def.version

    @property
    def observation_defs(self) -> tuple[ObservationDef, ...]:
        return tuple(self._template_def.observation_defs)

    @property
    def open_tree(self) -> ConditionTree:
        return self._open_tree

    @property
    def rules(self) -> tuple[CompiledRule, ...]:
        return self._rules

    @property
    def target_ids(self) -> frozenset[str]:
        """观测声明里的静态目标 ID。"""
        return frozenset(o.target_id for o in self._template_def.observation_defs)

    def hooks_at(self, mount_point: MountPoint) -> tuple[OperatorMountDef, ...]:
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
    mount: OperatorMountDef, operator_registry: OperatorRegistry, where: str, errors: list[str]
) -> OperatorMountDef | None:
    """校验算子挂载，返回参数规范化后的挂载。"""
    try:
        params = operator_registry.validate_mount(
            mount.operator, "event", mount.mount_point, mount.params
        )
    except OperatorError as e:
        errors.append(f"{where}: {e}")
        return None
    return mount.model_copy(update={"params": params.model_dump()})
