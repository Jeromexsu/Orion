"""目标基类与持久化记录。"""

import builtins
from collections.abc import Callable, Iterable
from typing import Any, ClassVar, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from core.observation import ObservedPoint, observed_point_name
from core.target.query_key import QueryKey, query_key_name, validate_query_value

_BASE_FIELDS = frozenset({"id", "type", "name", "aliases"})


class Target(BaseModel):
    """所有目标类型的基类。一个真实实体一条。

    每种目标类型（如船）继承它，放在 plugins/target/ 下，用 @target_type 声明类型名和观察点：

        @target_type("ship", observed_points=[Position, Draught])
        class Ship(Target):
            mmsi: str = provides(Mmsi)                      # 提供查询键 Mmsi
            imo: str | None = provides(Imo, default=None)   # 提供查询键 Imo，可为空
            flag: str | None = None                         # 普通属性

    - 属性字段用普通字段声明，构造时由 Pydantic 自动校验；id / name / aliases / type 由基类提供；
    - 能用来在上游认出目标的字段用 provides(...) 关联查询键，取值在构造时按查询键校验；
      上游按查询键（而不是字段名）判断能否查这个目标；
    - 观察点与目标类型无关，多种目标类型可共用。

    目标类型只由开发者通过代码定义和修改，不开放给用户在运行时配置。
    """

    # 不可变；写在 model_config 里（而不是类参数 frozen=True），子类就不必重复声明
    model_config = ConfigDict(frozen=True)

    type_name: ClassVar[str]                                       # 由 @target_type 设置
    observed_points: ClassVar[tuple[type[ObservedPoint], ...]] = ()  # 由 @target_type 设置

    type: str = ""              # 类型名，构造时按 type_name 自动填写
    id: str
    name: str                   # 展示名，报告里用
    aliases: list[str] = Field(default_factory=list[str])

    @classmethod
    def query_key_fields(cls) -> dict[builtins.type[QueryKey], str]:
        """这类目标用哪个字段提供哪个查询键，从字段的 Annotated 标注里读出。

        一个查询键只能由一个字段提供，否则抛 TypeError。
        """
        fields: dict[builtins.type[QueryKey], str] = {}
        for field_name, info in cls.model_fields.items():
            for meta in info.metadata:
                if isinstance(meta, type) and issubclass(meta, QueryKey):
                    query_key_name(meta)
                    if meta in fields:
                        raise TypeError(
                            f"{cls.__name__}: {meta.__name__} provided by both "
                            f"{fields[meta]!r} and {field_name!r}"
                        )
                    fields[meta] = field_name
        return fields

    def query_values(self) -> dict[builtins.type[QueryKey], Any]:
        """这个目标能提供的查询键及其取值；字段为空的不算。"""
        return {
            key: value
            for key, field_name in self.query_key_fields().items()
            if (value := getattr(self, field_name)) is not None
        }

    @model_validator(mode="before")
    @classmethod
    def _fill_type(cls, data: Any) -> Any:
        """type 不用手写：按 @target_type 声明的类型名自动填上；写了但不一致则拒绝。"""
        if isinstance(data, dict):
            name = type_name(cls)
            data = {**data}  # pyright: ignore[reportUnknownVariableType]
            data.setdefault("type", name)
            if data["type"] != name:
                raise ValueError(f"type must be {name!r}, got {data['type']!r}")
        return data  # pyright: ignore[reportUnknownVariableType]

    @model_validator(mode="after")
    def _validate_query_values(self) -> Self:
        for key, field_name in self.query_key_fields().items():
            value = getattr(self, field_name)
            if value is None:
                continue
            try:
                validate_query_value(key, value)
            except ValidationError as e:
                raise ValueError(f"{field_name}: not a valid {key.name}: {e}") from e
        return self

    def attributes(self) -> dict[str, Any]:
        """子类声明的属性字段（不含基类字段），持久化用。"""
        return self.model_dump(exclude=set(_BASE_FIELDS))

    def to_record(self) -> "TargetRecord":
        """转成与类型无关的持久化记录：子类属性字段收进 attributes。"""
        return TargetRecord(
            id=self.id,
            type=self.type,
            name=self.name,
            aliases=list(self.aliases),
            attributes=self.attributes(),
        )


class TargetRecord(BaseModel):
    """目标的持久化形态：与具体类型无关，持久化层不需要认识插件。

    由 TargetManager 按 type 还原成对应的 Target 子类。
    """

    model_config = ConfigDict(frozen=True)

    id: str
    type: str
    name: str
    aliases: list[str] = Field(default_factory=list[str])
    attributes: dict[str, Any] = Field(default_factory=dict[str, Any])


T = TypeVar("T", bound=Target)


def target_type(
    name: str, *, observed_points: Iterable[type[ObservedPoint]]
) -> Callable[[type[T]], type[T]]:
    """声明一个目标类型：类型名 + 可以在哪些观察点被观测。

    装饰时就检查声明：类型名非空、观察点声明完整、查询键关联合法，不合格抛 TypeError。
    """

    def decorate(cls: type[T]) -> type[T]:
        if not name:
            raise TypeError(f"{cls.__name__}: target type name must not be empty")
        points = tuple(observed_points)
        for point in points:
            observed_point_name(point)
        cls.type_name = name
        cls.observed_points = points
        cls.query_key_fields()
        return cls

    return decorate


def type_name(target_class: type[Target]) -> str:
    """读出类型名。没有用 @target_type 声明（包括只继承了父类声明的）抛 TypeError。"""
    name = target_class.__dict__.get("type_name")
    if not isinstance(name, str):
        raise TypeError(
            f"{target_class.__name__} must be declared with @target_type, "
            'e.g. @target_type("ship", observed_points=[Position])'
        )
    return name
