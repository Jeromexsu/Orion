"""目标基类与持久化记录。跨模块契约在 core.contracts。"""

from collections.abc import Mapping
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

_BASE_FIELDS = frozenset({"id", "type", "name", "aliases"})


class Target(BaseModel, frozen=True):
    """所有目标类型的基类。一个真实实体一条。

    每种目标类型（如飞机）继承它，放在 plugins/target/ 下：
    - 用 Literal 收窄 type 并给默认值，作为类型名：type: Literal["aircraft"] = "aircraft"
    - 用普通字段声明属性字段（如注册号），构造时由 Pydantic 自动校验
    - 用 focuses 声明关注点 → 该关注点下动态数据的 schema

    目标类型只由开发者通过代码定义和修改，不开放给用户在运行时配置。
    """

    focuses: ClassVar[Mapping[str, type[BaseModel]]] = {}

    type: str                   # 类型名，子类用 Literal 收窄
    id: str
    name: str                   # 展示名，报告里用
    aliases: list[str] = Field(default_factory=list[str])

    def attributes(self) -> dict[str, Any]:
        """子类声明的属性字段（不含基类字段），给 QuerySpec 和持久化用。"""
        return self.model_dump(exclude=set(_BASE_FIELDS))

    def to_record(self) -> "TargetRecord":
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
