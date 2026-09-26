class CollectorError(Exception):
    """collector 模块所有异常的基类。"""


class DuplicateAdapterError(CollectorError):
    pass


class UnknownAdapterError(CollectorError):
    pass
