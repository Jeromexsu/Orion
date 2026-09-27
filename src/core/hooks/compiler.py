from pydantic import ValidationError

from core.hooks.definitions import MountDef, MountPoint
from core.hooks.errors import MountCompileError, UnknownHookError
from core.hooks.mount import Mount
from core.hooks.registry import HookRegistry


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
        if MountPoint.RULE_HIT in at:
            errors.append("'rule_hit' is not a place of its own: list the rules in `rules`")
        places = at | ({MountPoint.RULE_HIT} if mount_def.rules else frozenset[MountPoint]())
        refused = sorted(str(p) for p in places - hook.mount_points)
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
