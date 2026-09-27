class HilError(Exception):
    """hil 模块所有异常的基类。"""


class ProposalNotFoundError(HilError):
    """提议不存在或已处理。"""


class ActionNotAllowedError(HilError):
    """提议的 action 不在白名单里。"""


class DuplicateActionError(HilError):
    pass
