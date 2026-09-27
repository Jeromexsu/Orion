from collections.abc import Set

from core.condition_engine import ConditionTree
from core.event.definitions import ObservationDef, OperatorMountDef, TemplateDef
from core.event.errors import TemplateScopeError
from core.operators import MountPoint


class CompiledRule:
    def __init__(
        self, name: str, tree: ConditionTree, hook_defs: tuple[OperatorMountDef, ...]
    ) -> None:
        self.name = name
        self.tree = tree
        self.hook_defs = hook_defs


class EventTemplate:
    """编译好的模板：不可变、带版本，持有开启条件树和每条规则的条件树。由 TemplateCompiler 构造。"""

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

