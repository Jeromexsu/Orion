class TargetError(Exception):
    """target 模块所有异常的基类。"""


class DuplicateTargetTypeError(TargetError):
    pass


class UnknownTargetTypeError(TargetError):
    pass


class TargetNotFoundError(TargetError):
    pass


class UnsupportedFocusError(TargetError):
    """目标类型没有声明这个关注点。"""


class NoUpstreamError(TargetError):
    """没有任何上游能服务这个 (type, focus) 组合。"""


class TargetInUseError(TargetError):
    """目标仍被某个 ObservableTarget 的订阅者引用，不能删除。"""


class TargetTypeChangeError(TargetError):
    """已存在的目标不能换类型——已有 ObservableTarget 的关注点和 schema 会失效。"""
