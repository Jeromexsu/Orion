class EventError(Exception):
    """event 模块所有异常的基类。"""


class TemplateCompileError(EventError):
    """模板定义不合法。errors 里每条都带定位（规则名 / 钩子序号）。"""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


class TemplateScopeError(EventError):
    """模板观测了父事件目标命名空间之外的目标。"""


class TemplateVersionError(EventError):
    """新定义的版本号没有比当前版本大。"""


class TemplateNotFoundError(EventError):
    pass


class TargetStillReferencedError(EventError):
    """目标仍被某个模板观测，不能从命名空间移除。"""


class ParentEventNotFoundError(EventError):
    pass


class DuplicateParentEventError(EventError):
    pass


class InstanceClosedError(EventError):
    pass
