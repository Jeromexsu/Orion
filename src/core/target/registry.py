from core.target.errors import DuplicateTargetTypeError, UnknownTargetTypeError
from core.target.target import Target, type_name


class TargetTypeRegistry:
    """Target types by type name. bootstrap registers the plugins.

    Observed points are not registered anywhere: a template names one together with a
    target, so it is looked up among that target type's observed_points.
    """

    def __init__(self) -> None:
        self._types: dict[str, type[Target]] = {}

    def register(self, target_class: type[Target]) -> None:
        """Register a target type.

        Raises:
            TypeError: If it is not declared with @target_type or its query key fields
                are invalid.
            DuplicateTargetTypeError: If the type name is taken.
        """
        name = type_name(target_class)
        target_class.query_key_fields()   # 检查查询键标注，不合法抛 TypeError
        if name in self._types:
            raise DuplicateTargetTypeError(name)
        self._types[name] = target_class

    def get(self, name: str) -> type[Target]:
        """Type name -> target type. Raises UnknownTargetTypeError if not registered."""
        try:
            return self._types[name]
        except KeyError:
            raise UnknownTargetTypeError(name) from None

    def types(self) -> list[type[Target]]:
        """Every registered target type."""
        return list(self._types.values())
