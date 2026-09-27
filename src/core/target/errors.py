class TargetError(Exception):
    """target 模块所有异常的基类。"""


class DuplicateTargetTypeError(TargetError):
    pass


class UnknownTargetTypeError(TargetError):
    pass


class TargetNotFoundError(TargetError):
    pass


class DuplicateObservedPointError(TargetError):
    """两个不同的观察点类用了同一个名字。"""


class UnknownObservedPointError(TargetError):
    pass


class UnsupportedObservedPointError(TargetError):
    """目标类型没有声明这个观察点。"""


class NoUpstreamError(TargetError):
    """没有任何上游能在这个观察点观测这个目标。"""


class UnsupportedUpstreamError(TargetError):
    """订阅了 ObservableTarget 上游列表之外的上游，或没指定任何上游。"""


class TargetInUseError(TargetError):
    """目标的某个 ObservableTarget 仍有订阅者，不能删除。"""


class TargetTypeChangeError(TargetError):
    """已存在的目标不能换类型——已有 ObservableTarget 的观察点可能失效。"""
