class TargetError(Exception):
    """target 模块所有异常的基类。"""


class DuplicateTargetTypeError(TargetError):
    pass


class UnknownTargetTypeError(TargetError):
    pass


class TargetNotFoundError(TargetError):
    pass


class DuplicateObservedPointError(TargetError):
    """两个不同的观察点类用了同一个名字（在已注册目标类型的声明里）。"""


class UnknownObservedPointError(TargetError):
    """没有任何已注册目标类型声明过这个观察点。"""


class TargetTypeChangeError(TargetError):
    """已存在的目标不能换类型——它在某些观察点上的可观测目标可能失效。"""
