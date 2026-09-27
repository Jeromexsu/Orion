class ObservableError(Exception):
    """observable 模块所有异常的基类。"""


class UnsupportedObservedPointError(ObservableError):
    """目标类型没有叫这个名字的观察点。"""


class NoUpstreamError(ObservableError):
    """没有任何上游能在这个观察点观测这个目标。"""


class UnsupportedUpstreamError(ObservableError):
    """订阅时没指定任何上游。"""
