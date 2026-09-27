from typing import Any

from core.hooks.errors import DuplicateHookError, UnknownHookError
from core.hooks.hook import Hook


class HookRegistry:
    """钩子注册表，按 Hook.name 索引。bootstrap 时注册插件。

    只注册和查找；挂载是否合法由 MountCompiler 检查。
    """

    def __init__(self) -> None:
        self._hooks: dict[str, Hook[Any]] = {}

    def register(self, hook: Hook[Any]) -> None:
        """没用 @hook 声明抛 TypeError；名字重复抛 DuplicateHookError。"""
        _check_declared(hook)
        if hook.name in self._hooks:
            raise DuplicateHookError(hook.name)
        self._hooks[hook.name] = hook

    def get(self, name: str) -> Hook[Any]:
        """未注册抛 UnknownHookError。"""
        try:
            return self._hooks[name]
        except KeyError:
            raise UnknownHookError(name) from None

    def hooks(self) -> list[Hook[Any]]:
        """已注册的全部钩子。"""
        return list(self._hooks.values())


def _check_declared(hook: Hook[Any]) -> None:
    """Raise TypeError unless the hook's class was declared with @hook."""
    attrs = ("name", "mount_points", "scopes", "proposes", "params_model")
    if not all(hasattr(hook, a) for a in attrs):
        raise TypeError(f"{type(hook).__name__} must be declared with @hook(...)")
