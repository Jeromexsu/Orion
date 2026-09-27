from typing import Protocol


class TargetReferrer(Protocol):
    """Something that refers to targets by ID and must be asked before one is removed.

    Defined here, implemented by the modules that refer to targets (e.g. observable's
    ObservableTargetManager); bootstrap adds them with TargetManager.add_referrer.
    TargetManager never learns what they are.
    """

    def references(self, target_id: str) -> list[str]:
        """What still uses the target, for the error message; empty if nothing does."""
        ...

    def release(self, target_id: str) -> None:
        """Drop what refers to the target, which nothing uses any more.

        Called only after every referrer returned no references, right before the
        target is removed.
        """
        ...
