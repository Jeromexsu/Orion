class TargetError(Exception):
    """target 模块所有异常的基类。"""


class DuplicateTargetTypeError(TargetError):
    pass


class UnknownTargetTypeError(TargetError):
    pass


class TargetNotFoundError(TargetError):
    pass


class TargetTypeChangeError(TargetError):
    """已存在的目标不能换类型——它在某些观察点上的可观测目标可能失效。"""
