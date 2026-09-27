from core.observation import ObservedPoint, observed_point_name
from core.target.errors import (
    DuplicateObservedPointError,
    DuplicateTargetTypeError,
    UnknownObservedPointError,
    UnknownTargetTypeError,
)
from core.target.target import Target, type_name


class TargetTypeRegistry:
    """Target types, and the observed points they declare. bootstrap registers the plugins.

    Observed points are not registered on their own: they are collected from the
    observed_points of each registered target type and looked up by name.
    """

    def __init__(self) -> None:
        self._types: dict[str, type[Target]] = {}
        self._observed_points: dict[str, type[ObservedPoint]] = {}

    def register(self, target_class: type[Target]) -> None:
        """Register a target type and collect the observed points it declares.

        Registers nothing if any check fails.

        Raises:
            TypeError: If it is not declared with @target_type or its query key fields
                are invalid.
            DuplicateTargetTypeError: If the type name is taken.
            DuplicateObservedPointError: If an observed point name already means
                another class.
        """
        name = type_name(target_class)
        target_class.query_key_fields()   # 检查查询键标注，不合法抛 TypeError
        if name in self._types:
            raise DuplicateTargetTypeError(name)
        points: dict[str, type[ObservedPoint]] = {}
        for point in target_class.observed_points:
            point_name = observed_point_name(point)
            known = self._observed_points.get(point_name) or points.get(point_name)
            if known is not None and known is not point:
                raise DuplicateObservedPointError(
                    f"{point_name!r} is both {known.__name__} and {point.__name__}"
                )
            points[point_name] = point
        self._types[name] = target_class
        self._observed_points.update(points)

    def get(self, name: str) -> type[Target]:
        """Type name -> target type. Raises UnknownTargetTypeError if not registered."""
        try:
            return self._types[name]
        except KeyError:
            raise UnknownTargetTypeError(name) from None

    def types(self) -> list[type[Target]]:
        """Every registered target type."""
        return list(self._types.values())

    def get_observed_point(self, name: str) -> type[ObservedPoint]:
        """Observed point name -> observed point.

        Raises UnknownObservedPointError if no registered target type declares it.
        """
        try:
            return self._observed_points[name]
        except KeyError:
            raise UnknownObservedPointError(name) from None

    def observed_points(self) -> list[type[ObservedPoint]]:
        """Every observed point declared by a registered target type."""
        return list(self._observed_points.values())
