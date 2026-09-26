from typing import Protocol, TypeVar

from pydantic import BaseModel

from core.contracts import Category, Level, MountPoint, Trigger
from core.operators.context import BaseContext

C = TypeVar("C", bound=BaseContext, contravariant=True)


class Operator(Protocol[C]):
    """算子接口。具体算子是插件，放在 plugins/operators/ 下。

    category 决定运行时拿到哪种上下文：progress → ProgressContext，
    discover / calibrate → SuggestContext，output → BaseContext。
    """

    @property
    def name(self) -> str:
        """模板里按名字引用，发布后不改。"""
        ...

    @property
    def category(self) -> Category: ...

    @property
    def levels(self) -> frozenset[Level]: ...

    @property
    def mount_points(self) -> frozenset[MountPoint]: ...

    @property
    def params_model(self) -> type[BaseModel]:
        """挂载时的参数，如阈值。"""
        ...

    def run(self, trigger: Trigger, ctx: C) -> None: ...
