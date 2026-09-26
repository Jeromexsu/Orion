class OperatorError(Exception):
    """operators 模块所有异常的基类。"""


class DuplicateOperatorError(OperatorError):
    pass


class UnknownOperatorError(OperatorError):
    pass


class InvalidMountError(OperatorError):
    """算子不支持该层级/挂载点，或参数不合法。"""
