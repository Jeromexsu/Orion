class HookError(Exception):
    """hooks 模块所有异常的基类。"""


class DuplicateHookError(HookError):
    pass


class UnknownHookError(HookError):
    pass


class UndeclaredCapabilityError(HookError):
    """钩子用了没有声明的能力（如没声明 scopes={"event"} 却访问 ctx.event）。"""


class MountCompileError(HookError):
    """A mount does not fit the hook's declaration."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors
