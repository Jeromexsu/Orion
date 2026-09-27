"""Mount: a hook compiled into the places a template put it, with typed parameters."""

from typing import Any

from pydantic import BaseModel

from core.hooks.definitions import MountPoint
from core.hooks.hook import Hook


class Mount:
    """A compiled mount: the hook itself, its validated parameters and where it runs.

    Built by MountCompiler; the event runs it without looking anything up and keeps its
    state under name.
    """

    def __init__(
        self,
        name: str,
        hook: Hook[Any],
        params: BaseModel,
        at: frozenset[MountPoint],
        rules: frozenset[str],
    ) -> None:
        self.name = name
        self.hook = hook
        self.params = params
        self.at = at            # mount points of the event (never rule_hit)
        self.rules = rules      # rules whose rule_hit it runs at
