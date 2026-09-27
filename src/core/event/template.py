from core.condition_engine import ConditionTree
from core.event.definitions import ObservableDef, TemplateDef
from core.hooks import Mount, MountPoint
from core.observable import ObservableTarget


class CompiledObservable:
    """编译后的可观测目标声明：解析好的可观测目标 + 要订阅的上游。

    只引用可观测目标（由 TargetManager 保证单例），不改它的状态；订阅由 runner 执行。
    """

    def __init__(self, observable: ObservableTarget, upstreams: frozenset[str]) -> None:
        self.observable = observable
        self.upstreams = upstreams


class CompiledRule:
    """编译后的规则：规则名 + 条件树 + 命中时跑的挂载（rules 里列了这条规则的挂载，按声明顺序）。"""

    def __init__(self, name: str, tree: ConditionTree, mounts: tuple[Mount, ...]) -> None:
        self.name = name
        self.tree = tree
        self.mounts = mounts


class EventTemplate:
    """编译好的模板：不可变、带版本。由 TemplateCompiler 构造。

    持有解析好的可观测目标、开启条件树、每条规则的条件树和编译好的挂载。
    """

    def __init__(
        self,
        template_def: TemplateDef,
        compiled_observables: tuple[CompiledObservable, ...],
        open_tree: ConditionTree,
        rules: tuple[CompiledRule, ...],
        mounts: tuple[Mount, ...],
    ) -> None:
        self._template_def = template_def
        self._compiled_observables = compiled_observables
        self._open_tree = open_tree
        self._rules = rules
        self._mounts = mounts

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
    def observable_defs(self) -> tuple[ObservableDef, ...]:
        return tuple(self._template_def.observable_defs)

    @property
    def compiled_observables(self) -> tuple[CompiledObservable, ...]:
        """runner 要订阅的：每项是可观测目标 + 要订阅的上游。"""
        return self._compiled_observables

    @property
    def open_tree(self) -> ConditionTree:
        return self._open_tree

    @property
    def rules(self) -> tuple[CompiledRule, ...]:
        return self._rules

    @property
    def target_ids(self) -> frozenset[str]:
        """可观测目标声明里的静态目标 ID。"""
        return self._template_def.target_ids

    def mounts_at(self, mount_point: MountPoint) -> tuple[Mount, ...]:
        """at 里有这个挂载点的挂载，按声明顺序（rule_hit 的挂载在各规则上）。"""
        return tuple(m for m in self._mounts if mount_point in m.at)
