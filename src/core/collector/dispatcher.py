import logging

from core.target import ObservableTarget, Observation

logger = logging.getLogger(__name__)


class Dispatcher:
    """把一条观测交给订阅了其来源上游的订阅者。"""

    def dispatch(self, observable: ObservableTarget, observation: Observation) -> int:
        """逐个调用 on_observation，每个订阅者单独隔离异常。返回失败的订阅者数。"""
        failures = 0
        for referencer in observable.referencers_for(observation.upstream):
            try:
                referencer.on_observation(observation)
            except Exception:
                failures += 1
                logger.exception("referencer %r failed on %s", referencer, observation.source_id)
        return failures
