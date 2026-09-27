"""钩子：挂在子事件生命周期上的可插拔动作。

负责：钩子基类与声明（@hook）；注册；挂载（definitions.MountDef --compiler.MountCompiler--> mount.Mount，
      对照钩子自己的声明检查）；
      按声明组装的上下文（能力没声明就用不了）；调用时机（Occasion）。
      钩子何时被调用由 event 决定，这里不调度；挂载名是否唯一、引用的规则是否存在由模板编译器检查。
两个正交的维度：直接作用于哪些作用域（external / event），能否提议（经 hil 审核；parent / target 只能走这条）。
对外：Hook、hook、HookContext、EventHandle、Occasion 及各挂载点的时机类型、HookRegistry、
      MountDef / Mount / MountCompiler、
      ProposalSink（提议的去处，由 hil 实现）。
依赖：observation（ObservationEnvelope）、condition_engine（EvalResult）、hil（Proposal）。
扩展点：plugins/hooks/ 下继承 Hook[参数模型]，用 @hook 声明。
"""

from core.hooks.compiler import MountCompiler
from core.hooks.context import EventHandle, HookContext
from core.hooks.definitions import MountDef, MountPoint
from core.hooks.errors import (
    DuplicateHookError,
    HookError,
    MountCompileError,
    UndeclaredCapabilityError,
    UnknownHookError,
)
from core.hooks.hook import (
    DIRECT_SCOPES,
    Hook,
    NoParams,
    Scope,
    hook,
)
from core.hooks.mount import Mount
from core.hooks.occasion import (
    ClosedOccasion,
    CreatedOccasion,
    ObservationOccasion,
    Occasion,
    RuleHitOccasion,
)
from core.hooks.registry import HookRegistry
from core.hooks.sink import ProposalSink

__all__ = [
    "DIRECT_SCOPES",
    "ClosedOccasion",
    "CreatedOccasion",
    "DuplicateHookError",
    "EventHandle",
    "Mount",
    "MountCompileError",
    "MountCompiler",
    "MountDef",
    "MountPoint",
    "NoParams",
    "ObservationOccasion",
    "Occasion",
    "Hook",
    "HookContext",
    "HookError",
    "HookRegistry",
    "RuleHitOccasion",
    "Scope",
    "ProposalSink",
    "UndeclaredCapabilityError",
    "UnknownHookError",
    "hook",
]
