"""Mounts: a hook put at a mount point with parameters.

As written in a template (MountDef) and compiled against the hook's declaration (Mount).
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from core.hooks.errors import MountCompileError, UnknownHookError
from core.hooks.hook import Hook, MountPoint
from core.hooks.registry import HookRegistry


class MountDef(BaseModel):
    """Mount a hook at a mount point, as written in a template."""

    model_config = ConfigDict(frozen=True)

    hook: str                   # hook name in the HookRegistry
    mount_point: MountPoint
    params: dict[str, Any] = Field(default_factory=dict[str, Any])


class Mount:
    """A compiled mount: the hook itself, its validated parameters and where it is
    mounted. Built by MountCompiler; the event runs it without looking anything up."""

    def __init__(self, hook: Hook[Any], params: BaseModel, mount_point: MountPoint) -> None:
        self.hook = hook
        self.params = params
        self.mount_point = mount_point


class MountCompiler:
    """Compile MountDefs into Mounts against the registered hooks.

    Only checks the mount against the hook's own declaration; where a mount point is
    allowed in a template (rule_hit only on rules) is the template compiler's call.
    """

    def __init__(self, hook_registry: HookRegistry) -> None:
        self._hook_registry = hook_registry

    def compile(self, mount_def: MountDef) -> Mount:
        """Compile one mount.

        Raises:
            MountCompileError: If the hook is unknown, cannot be mounted at this mount
                point, or the parameters do not validate against its params_model.
        """
        try:
            hook = self._hook_registry.get(mount_def.hook)
        except UnknownHookError:
            raise MountCompileError([f"unknown hook {mount_def.hook!r}"]) from None
        if mount_def.mount_point not in hook.mount_points:
            raise MountCompileError([f"{hook.name} cannot mount at {mount_def.mount_point!r}"])
        try:
            params = hook.params_model.model_validate(mount_def.params)
        except ValidationError as e:
            raise MountCompileError([f"invalid params for {hook.name}: {e}"]) from None
        return Mount(hook, params, mount_def.mount_point)
