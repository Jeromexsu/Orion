"""记录收到什么的订阅者。"""

from core.observation import ObservationEnvelope


class Subscriber:
    def __init__(self) -> None:
        self.received: list[ObservationEnvelope] = []

    def on_observation(self, envelope: ObservationEnvelope) -> None:
        self.received.append(envelope)
