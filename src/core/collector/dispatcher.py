import logging

from core.contracts import DynamicData
from core.target import ObservableTarget

logger = logging.getLogger(__name__)


class Dispatcher:
    """把一条动态数据交给订阅了其来源上游的订阅者。"""

    def dispatch(self, observable: ObservableTarget, data: DynamicData) -> int:
        """逐个调用 on_data，每个订阅者单独隔离异常。返回失败的订阅者数。"""
        failures = 0
        for referencer in observable.referencers_for(data.upstream):
            try:
                referencer.on_data(data)
            except Exception:
                failures += 1
                logger.exception("referencer %r failed on %s", referencer, data.source_id)
        return failures
