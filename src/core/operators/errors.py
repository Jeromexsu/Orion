class OperatorError(Exception):
    """operators 模块所有异常的基类。"""


class DuplicateOperatorError(OperatorError):
    pass


class UnknownOperatorError(OperatorError):
    pass


class UndeclaredCapabilityError(OperatorError):
    """算子用了没有声明的能力（如没声明 scopes={"event"} 却访问 ctx.event）。"""
