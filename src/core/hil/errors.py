class HilError(Exception):
    """hil 模块所有异常的基类。"""


class ProposalNotFoundError(HilError):
    """提议不存在或已处理。"""


class ActionNotAllowedError(HilError):
    """提议的 action 不在白名单里。"""


class InvalidProposalArgsError(HilError):
    """提议的参数（或分析师改过的参数）不符合动作的参数模型。"""


class DuplicateActionError(HilError):
    pass
