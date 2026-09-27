class CollectorError(Exception):
    """collector 模块所有异常的基类。"""


class DuplicateUpstreamAdapterError(CollectorError):
    pass


class UnknownUpstreamAdapterError(CollectorError):
    pass
