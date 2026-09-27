class ReportError(Exception):
    """report 模块所有异常的基类。"""


class ReportNotFoundError(ReportError):
    pass


class ReportLockedError(ReportError):
    """报告已被分析师接手或已发出，不能再按当前方式修改。"""
