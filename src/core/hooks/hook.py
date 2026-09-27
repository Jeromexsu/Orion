"""The hook extension point: the Hook base class and @hook."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from enum import StrEnum
from typing import Any, ClassVar, Generic, TypeVar, get_args, get_origin

from pydantic import BaseModel

from core.hooks.context import HookContext, Occasion
from core.hooks.definitions import MountPoint


class Scope(StrEnum):
    """作用域：钩子影响哪一块。"""

    EXTERNAL = "external"   # 系统外部：报告、通知（输出通道构造时注入）
    EVENT = "event"         # 子事件（ctx.event）
    PARENT = "parent"       # 父事件：只能提议
    TARGET = "target"       # 目标：只能提议

# 可以直接作用的作用域；parent / target 只能经审核（proposes=True）改动
DIRECT_SCOPES: frozenset[Scope] = frozenset({Scope.EXTERNAL, Scope.EVENT})

P = TypeVar("P", bound=BaseModel)


class NoParams(BaseModel):
    """Parameters of a hook that takes none."""


class Hook(ABC, Generic[P]):
    """钩子：挂在子事件生命周期上的动作。每种一个子类，放在 plugins/hooks/ 下，用 @hook 声明：

        @hook(mount_points={MountPoint.RULE_HIT}, scopes={Scope.EVENT})
        class CountHits(Hook[CountHitsParams]):
            def run(self, params, ctx, occasion): ...

    两个正交的维度：直接作用于哪些作用域（scopes，只能是 external / event），能不能提议
    （proposes，经审核后生效，影响哪个作用域由提议的动作决定）。什么都不声明的钩子不影响系统。
    name 默认类名首字母小写（CountHits → "countHits"）；参数模型取泛型参数（CountHitsParams）。
    """

    name: ClassVar[str]                             # 由 @hook 设置；模板里按名字引用
    mount_points: ClassVar[frozenset[MountPoint]]   # 由 @hook 设置；可以挂在哪些挂载点
    scopes: ClassVar[frozenset[Scope]]              # 由 @hook 设置；直接作用于哪些作用域
    proposes: ClassVar[bool]                        # 由 @hook 设置；能否提议（经审核）
    params_model: ClassVar[type[BaseModel]]         # 由 @hook 设置；挂载参数的形状

    @abstractmethod
    def run(self, params: P, ctx: HookContext, occasion: Occasion) -> dict[str, Any] | None:
        """Run once. Exceptions are isolated and logged by the event.

        Args:
            params: This mount's parameters, validated against params_model at compile time.
            ctx: This mount's state (a copy), read-only information about the event, and
                the capabilities it declared.
            occasion: Why it is being run — the mount point and what happened there;
                match on its type to get the fields that mount point always has.

        Returns:
            The mount's new state, which the event stores in place of the old one;
            None to leave it unchanged. One mount has one state across every place it is
            mounted, so a hook mounted at several places can carry what it saw between them.
        """
        ...


O = TypeVar("O", bound=Hook[Any])


def hook(
    *,
    mount_points: Iterable[MountPoint],
    scopes: Iterable[Scope] = (),
    proposes: bool = False,
    name: str | None = None,
    params: type[BaseModel] | None = None,
) -> Callable[[type[O]], type[O]]:
    """Declare a hook.

    Args:
        mount_points: Where it can be mounted (at least one).
        scopes: Scopes it affects directly: "external" (outputs, through channels
            injected at construction) and/or "event" (gives ctx.event). "parent" and
            "target" cannot be changed directly; use proposes.
        proposes: Whether it may make proposals for review (gives ctx.propose).
        name: Name templates refer to it by. Defaults to the class name with its first
            letter lowered (CountHits -> "countHits").
        params: The mount parameter model. Defaults to the generic argument of the base
            (Hook[CountHitsParams] -> CountHitsParams).

    Raises:
        TypeError: If the declaration is incomplete or asks for a scope that can only
            be changed through proposals.
    """

    def decorate(cls: type[O]) -> type[O]:
        points = frozenset(mount_points)
        if not points:
            raise TypeError(f"{cls.__name__}: mount_points needs at least one mount point")
        declared = frozenset(scopes)
        indirect = sorted(declared - DIRECT_SCOPES)
        if indirect:
            raise TypeError(
                f"{cls.__name__}: {indirect} can only be changed through proposals "
                "(proposes=True), not directly"
            )
        model = params if params is not None else _params_argument(cls)
        if model is None:
            raise TypeError(f"{cls.__name__}: subclass Hook[SomeParams] or pass params=...")
        cls.name = name if name is not None else cls.__name__[:1].lower() + cls.__name__[1:]
        cls.mount_points = points
        cls.scopes = declared
        cls.proposes = proposes
        cls.params_model = model
        return cls

    return decorate


def _params_argument(cls: type[Any]) -> type[BaseModel] | None:
    for base in getattr(cls, "__orig_bases__", ()):
        if get_origin(base) is Hook:
            (argument,) = get_args(base)
            if isinstance(argument, type) and issubclass(argument, BaseModel):
                return argument
    return None
