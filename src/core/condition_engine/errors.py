class ConditionEngineError(Exception):
    """condition engine 所有异常的基类。"""


class DuplicateEvaluatorError(ConditionEngineError):
    pass


class UnknownEvaluatorError(ConditionEngineError):
    pass


class ConditionCompileError(ConditionEngineError):
    """条件定义语义不合法。errors 里每条都带节点路径，便于前端定位。"""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors
