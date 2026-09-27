from core.condition_engine import (
    ConditionCompileError,
    ConditionCompiler,
    ConditionDef,
    ConditionTree,
)
from core.event.definitions import TemplateDef
from core.event.errors import TemplateCompileError
from core.event.template import CompiledObservable, CompiledRule, EventTemplate
from core.event.upstream import UpstreamCatalog
from core.hooks import Mount, MountCompileError, MountCompiler
from core.observable import ObservableTargetFactory
from core.observation import Observation
from core.target import TargetError, TargetManager


class TemplateCompiler:
    """把模板定义（TemplateDef）编译成 EventTemplate。依赖在构造时注入一次。"""

    def __init__(
        self,
        condition_compiler: ConditionCompiler,
        mount_compiler: MountCompiler,
        target_manager: TargetManager,
        upstream_catalog: UpstreamCatalog,
        observable_target_factory: ObservableTargetFactory,
    ) -> None:
        self._condition_compiler = condition_compiler
        self._mount_compiler = mount_compiler
        self._target_manager = target_manager
        self._upstream_catalog = upstream_catalog
        self._observable_target_factory = observable_target_factory

    def compile(self, template_def: TemplateDef) -> EventTemplate:
        """编译并校验整个模板，所有错误一次收集进 TemplateCompileError。

        分两个阶段：先只校验、不产生副作用（可观测目标声明只读目标、问 UpstreamCatalog 检查，
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

        trees: dict[str, ConditionTree] = {}
        for rule in template_def.rule_defs:
            tree = compile_tree(f"rule {rule.name!r}", rule.condition_def)
            if tree is not None:
                trees[rule.name] = tree

        mounts = self._compile_mounts(template_def, set(names), errors)
        rules = tuple(
            CompiledRule(name, tree, tuple(m for m in mounts if name in m.rules))
            for name, tree in trees.items()
        )

        if errors or open_tree is None:
            raise TemplateCompileError(errors)
        compiled_observables = self._compile_observables(template_def)
        return EventTemplate(
            template_def, compiled_observables, open_tree, rules, mounts
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
                target = self._target_manager.get_target(o.target_id)
            except TargetError as e:
                errors.append(f"{where}: {e}")
                continue
            point = type(target).find_observed_point(o.observed_point)
            if point is None:
                errors.append(f"{where}: {target.type} has no observed point {o.observed_point!r}")
                continue
            available = self._upstream_catalog.upstreams_for(target, point)
            if not available:
                errors.append(f"{where}: no upstream can observe it")
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
                self._observable_target_factory.get_observable(o.target_id, o.observed_point),
                frozenset(o.upstreams),
            )
            for o in template_def.observable_defs
        )

    def _compile_mounts(
        self, template_def: TemplateDef, rule_names: set[str], errors: list[str]
    ) -> tuple[Mount, ...]:
        """Compile every mount of the template, collecting errors instead of raising.

        Besides what MountCompiler checks against the hook, checks what only the template
        knows: mount names are unique (each keys a state) and the rules exist.

        Args:
            rule_names: Rule names declared in the template.
            errors: Collects every error found. Appended to; nothing is raised.

        Returns:
            The mounts that compiled, in declaration order.
        """
        names = [m.mount_name for m in template_def.mount_defs]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            errors.append(f"duplicate mount names {dupes}: give them distinct `name`s")

        mounts: list[Mount] = []
        for mount_def in template_def.mount_defs:
            where = f"mount {mount_def.mount_name!r}"
            unknown = sorted(set(mount_def.rules) - rule_names)
            if unknown:
                errors.append(f"{where}: unknown rules {unknown}")
            try:
                mounts.append(self._mount_compiler.compile(mount_def))
            except MountCompileError as e:
                errors.extend(f"{where}: {msg}" for msg in e.errors)
        return tuple(mounts)
