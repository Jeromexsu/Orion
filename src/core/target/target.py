"""目标基类与持久化记录。"""

import builtins
from typing import Any, ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from core.target.observed_point import ObservedPoint
from core.target.query_key import QueryKey, query_key_name, validate_query_value

_BASE_FIELDS = frozenset({"id", "type", "name", "aliases"})


class Target(BaseModel, frozen=True):
    """所有目标类型的基类。一个真实实体一条。

    每种目标类型（如飞机）继承它，放在 plugins/target/ 下：
    - 用 Literal 收窄 type 并给默认值，作为类型名：type: Literal["aircraft"] = "aircraft"
    - 用普通字段声明属性字段（如注册号），构造时由 Pydantic 自动校验
    - 用 observed_points 声明这类目标可以在哪些观察点被观测（观察点与目标类型无关，可共用）
    - 在能提供查询键的字段上用 Annotated 标注查询键：icao24: Annotated[str | None, Icao24] = None；
      上游按查询键（而不是字段名）判断能否查这个目标，取值在构造时按查询键校验

    目标类型只由开发者通过代码定义和修改，不开放给用户在运行时配置。
    """

    observed_points: ClassVar[tuple[type[ObservedPoint], ...]] = ()

    type: str                   # 类型名，子类用 Literal 收窄
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
        """子类声明的属性字段（不含基类字段），给 QuerySpec 和持久化用。"""
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


def type_name(target_class: type[Target]) -> str:
    """读出子类的类型名（type 字段的默认值）。"""
    default = target_class.model_fields["type"].default
    if not isinstance(default, str) or not default:
        raise TypeError(
            f"{target_class.__name__} must narrow `type` with a Literal default, "
            'e.g. type: Literal["aircraft"] = "aircraft"'
        )
    return default
