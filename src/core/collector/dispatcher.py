import logging

from core.target import ObservableTarget, ObservationEnvelope

logger = logging.getLogger(__name__)


class Dispatcher:
    """把一条观测交给订阅了其来源上游的订阅者。"""

    def dispatch(self, observable: ObservableTarget, envelope: ObservationEnvelope) -> int:
        """逐个调用 on_observation，每个订阅者单独隔离异常。返回失败的订阅者数。"""
        failures = 0
        for subscriber in observable.subscribers_for(envelope.upstream):
            try:
                subscriber.on_observation(envelope)
            except Exception:
                failures += 1
                logger.exception("subscriber %r failed on %s", subscriber, envelope.source_id)
        return failures
