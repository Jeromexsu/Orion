from core.condition_engine import (
    ConditionCompileError,
    ConditionCompiler,
    ConditionDef,
    ConditionTree,
)
from core.event.definitions import OperatorMountDef, TemplateDef
from core.event.errors import TemplateCompileError
from core.event.template import CompiledObservable, CompiledRule, EventTemplate
from core.operators import OperatorError, OperatorRegistry
from core.target import TargetError, TargetManager


class TemplateCompiler:
    """把模板定义（TemplateDef）编译成 EventTemplate。依赖在构造时注入一次。"""

    def __init__(
        self,
        condition_compiler: ConditionCompiler,
        operator_registry: OperatorRegistry,
        targets: TargetManager,
    ) -> None:
        self._condition_compiler = condition_compiler
        self._operator_registry = operator_registry
        self._targets = targets

    def compile(self, template_def: TemplateDef) -> EventTemplate:
        """编译并校验整个模板，所有错误一次收集进 TemplateCompileError。

        可观测目标声明按 TargetManager 解析：目标与观察点存在、上游可用；观察点返回的观测有哪些字段，
        交给条件引擎，因此条件只能引用已声明的观测，且判断方式需要的字段必须存在。
        """
        errors: list[str] = []
        observables = self._resolve_observables(template_def, errors)
        fields_by_observable = {
            c.observable.id: set(c.observable.observed_point.observation.model_fields)
            for c in observables
        }

        def compile_tree(where: str, condition_def: ConditionDef) -> ConditionTree | None:
            try:
                return self._condition_compiler.compile(condition_def, fields_by_observable)
            except ConditionCompileError as e:
                errors.extend(f"{where}: {msg}" for msg in e.errors)
                return None

        open_tree = compile_tree("open_condition_def", template_def.open_condition_def)

        names = [r.name for r in template_def.rule_defs]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            errors.append(f"duplicate rule names {dupes}")

        rules: list[CompiledRule] = []
        for rule in template_def.rule_defs:
            tree = compile_tree(f"rule {rule.name!r}", rule.condition_def)
            hooks: list[OperatorMountDef] = []
            for i, mount in enumerate(rule.hook_defs):
                where = f"rule {rule.name!r} hook {i}"
                if mount.mount_point != "rule_hit":
                    errors.append(f"{where}: rule hooks must mount at 'rule_hit'")
                    continue
                bound = self._bind(mount, where, errors)
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
            bound = self._bind(mount, where, errors)
            if bound is not None:
                template_hooks.append(bound)

        if errors or open_tree is None:
            raise TemplateCompileError(errors)
        return EventTemplate(
            template_def, observables, open_tree, tuple(rules), tuple(template_hooks)
        )

    def _resolve_observables(
        self, template_def: TemplateDef, errors: list[str]
    ) -> tuple[CompiledObservable, ...]:
        """解析可观测目标声明：目标与观察点存在、上游可用。"""
        resolved: dict[str, CompiledObservable] = {}
        for o in template_def.observable_defs:
            where = f"observable_def {o.observable_id!r}"
            if o.observable_id in resolved:
                errors.append(f"{where}: duplicate")
                continue
            try:
                observable = self._targets.get_observable(o.target_id, o.observed_point)
            except TargetError as e:
                errors.append(f"{where}: {e}")
                continue
            unavailable = sorted(set(o.upstreams) - set(observable.upstreams))
            if unavailable:
                errors.append(
                    f"{where}: upstreams {unavailable} not in available "
                    f"{list(observable.upstreams)}"
                )
            resolved[observable.id] = CompiledObservable(observable, frozenset(o.upstreams))
        return tuple(resolved.values())

    def _bind(
        self, mount: OperatorMountDef, where: str, errors: list[str]
    ) -> OperatorMountDef | None:
        """校验算子挂载，返回参数规范化后的挂载。"""
        try:
            params = self._operator_registry.validate_mount(
                mount.operator, "event", mount.mount_point, mount.params
            )
        except OperatorError as e:
            errors.append(f"{where}: {e}")
            return None
        return mount.model_copy(update={"params": params.model_dump()})
