"""Mounts: a hook put at one or more places in a template, with parameters.

As written in a template (MountDef) and compiled against the hook's declaration (Mount).
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from core.hooks.errors import MountCompileError, UnknownHookError
from core.hooks.hook import Hook, MountPoint
from core.hooks.registry import HookRegistry


class MountDef(BaseModel):
    """Mount a hook at one or more places, as written in a template.

    The places are the event's mount points in `at` plus the rule_hit of each rule in
    `rules`. One mount has one state across all of them.
    """

    model_config = ConfigDict(frozen=True)

    hook: str                   # hook name in the HookRegistry
    name: str | None = None     # unique in the template; defaults to the hook name
    at: list[MountPoint] = Field(default_factory=list[MountPoint])   # rule_hit goes in rules
    rules: list[str] = Field(default_factory=list[str])              # rule names, run at rule_hit
    params: dict[str, Any] = Field(default_factory=dict[str, Any])

    @property
    def mount_name(self) -> str:
        """The name the mount's state is kept under."""
        return self.name if self.name is not None else self.hook


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


class MountCompiler:
    """Compile MountDefs into Mounts against the registered hooks.

    Only checks the mount against the hook's own declaration. Whether the rules exist and
    the names are unique within a template is the template compiler's call.
    """

    def __init__(self, hook_registry: HookRegistry) -> None:
        self._hook_registry = hook_registry

    def compile(self, mount_def: MountDef) -> Mount:
        """Compile one mount.

        Raises:
            MountCompileError: With every problem found: unknown hook, no place to run,
                rule_hit in `at`, a place the hook cannot be mounted at, invalid params.
        """
        try:
            hook = self._hook_registry.get(mount_def.hook)
        except UnknownHookError:
            raise MountCompileError([f"unknown hook {mount_def.hook!r}"]) from None

        errors: list[str] = []
        at = frozenset(mount_def.at)
        if not at and not mount_def.rules:
            errors.append("mounted nowhere: give `at` and/or `rules`")
        if "rule_hit" in at:
            errors.append("'rule_hit' is not a place of its own: list the rules in `rules`")
        places = at | ({"rule_hit"} if mount_def.rules else frozenset[MountPoint]())
        refused = sorted(places - hook.mount_points)
        if refused:
            errors.append(f"{hook.name} cannot mount at {refused}")
        try:
            params = hook.params_model.model_validate(mount_def.params)
        except ValidationError as e:
            errors.append(f"invalid params for {hook.name}: {e}")
            params = None
        if errors or params is None:
            raise MountCompileError(errors)
        return Mount(mount_def.mount_name, hook, params, at, frozenset(mount_def.rules))
