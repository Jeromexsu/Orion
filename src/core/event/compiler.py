from pydantic import ValidationError

from core.condition_engine import (
    ConditionCompileError,
    ConditionCompiler,
    ConditionDef,
    ConditionTree,
)
from core.event.definitions import OperatorMountDef, TemplateDef
from core.event.errors import TemplateCompileError
from core.event.template import CompiledObservable, CompiledRule, EventTemplate, Hook
from core.operators import OperatorRegistry, UnknownOperatorError
from core.target import Observation, TargetError, TargetManager


class TemplateCompiler:
    """把模板定义（TemplateDef）编译成 EventTemplate。依赖在构造时注入一次。"""

    def __init__(
        self,
        condition_compiler: ConditionCompiler,
        operator_registry: OperatorRegistry,
        target_manager: TargetManager,
    ) -> None:
        self._condition_compiler = condition_compiler
        self._operator_registry = operator_registry
        self._target_manager = target_manager

    def compile(self, template_def: TemplateDef) -> EventTemplate:
        """编译并校验整个模板，所有错误一次收集进 TemplateCompileError。

        分两个阶段：先只校验、不产生副作用（可观测目标声明用 TargetManager.inspect_observable 检查，
        观察点产出的观测类交给条件编译器）；全部通过后，才取得（必要时创建）可观测目标。
        因此被拒绝的模板不会留下可观测目标。
        """
        errors: list[str] = []
        declared_observables = self._check_observables(template_def, errors)

        def compile_tree(where: str, condition_def: ConditionDef) -> ConditionTree | None:
            try:
                return self._condition_compiler.compile(condition_def, declared_observables)
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
            hooks: list[Hook] = []
            for i, mount_def in enumerate(rule.hook_defs):
                where = f"rule {rule.name!r} hook {i}"
                if mount_def.mount_point != "rule_hit":
                    errors.append(f"{where}: rule hooks must mount at 'rule_hit'")
                    continue
                hook = self._compile_hook(mount_def, where, errors)
                if hook is not None:
                    hooks.append(hook)
            if tree is not None:
                rules.append(CompiledRule(rule.name, tree, tuple(hooks)))

        template_hooks: list[Hook] = []
        for i, mount_def in enumerate(template_def.hook_defs):
            where = f"hook {i}"
            if mount_def.mount_point == "rule_hit":
                errors.append(f"{where}: 'rule_hit' hooks belong on a rule")
                continue
            hook = self._compile_hook(mount_def, where, errors)
            if hook is not None:
                template_hooks.append(hook)

        if errors or open_tree is None:
            raise TemplateCompileError(errors)
        compiled_observables = self._compile_observables(template_def)
        return EventTemplate(
            template_def, compiled_observables, open_tree, tuple(rules), tuple(template_hooks)
        )

    def _check_observables(
        self, template_def: TemplateDef, errors: list[str]
    ) -> dict[str, type[Observation]]:
        """校验可观测目标声明（不创建可观测目标），返回「可观测目标 ID → 它产出的观测类」。"""
        declared_observables: dict[str, type[Observation]] = {}
        for o in template_def.observable_defs:
            where = f"observable_def {o.observable_id!r}"
            if o.observable_id in declared_observables:
                errors.append(f"{where}: duplicate")
                continue
            try:
                point, available = self._target_manager.inspect_observable(
                    o.target_id, o.observed_point
                )
            except TargetError as e:
                errors.append(f"{where}: {e}")
                continue
            unavailable = sorted(set(o.upstreams) - set(available))
            if unavailable:
                errors.append(f"{where}: upstreams {unavailable} not in available {list(available)}")
            declared_observables[o.observable_id] = point.observation
        return declared_observables

    def _compile_observables(self, template_def: TemplateDef) -> tuple[CompiledObservable, ...]:
        """全部校验通过后调用：取得（必要时创建）可观测目标，组装 runner 要订阅的项。"""
        return tuple(
            CompiledObservable(
                self._target_manager.get_observable(o.target_id, o.observed_point),
                frozenset(o.upstreams),
            )
            for o in template_def.observable_defs
        )

    def _compile_hook(
        self, mount_def: OperatorMountDef, where: str, errors: list[str]
    ) -> Hook | None:
        """Check an operator mount and compile it into a hook.

        Checks that the operator exists, that it can be mounted at this mount point and
        that the parameters are valid against its params_model.

        Args:
            mount_def: The operator mount as written in the template.
            where: Location prefix for error messages (e.g. "rule 'enter' hook 0").
            errors: Collects every error found. Appended to; nothing is raised.

        Returns:
            The hook, or None if any check failed.
        """
        try:
            operator = self._operator_registry.get(mount_def.operator)
        except UnknownOperatorError:
            errors.append(f"{where}: unknown operator {mount_def.operator!r}")
            return None
        if mount_def.mount_point not in operator.mount_points:
            errors.append(f"{where}: {operator.name} cannot mount at {mount_def.mount_point!r}")
            return None
        try:
            params = operator.params_model.model_validate(mount_def.params)
        except ValidationError as e:
            errors.append(f"{where}: invalid params for {operator.name}: {e}")
            return None
        return Hook(operator, params, mount_def.mount_point)
