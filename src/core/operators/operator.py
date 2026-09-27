from typing import Protocol, TypeVar

from pydantic import BaseModel

from core.operators.context import BaseContext
from core.operators.trigger import Category, Level, MountPoint, Trigger

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
    def category(self) -> Category:
        """算子类别，决定拿到哪种上下文。"""
        ...

    @property
    def levels(self) -> frozenset[Level]:
        """可以挂在哪些层级（父事件 / 子事件）。"""
        ...

    @property
    def mount_points(self) -> frozenset[MountPoint]:
        """可以挂在哪些挂载点。"""
        ...

    @property
    def params_model(self) -> type[BaseModel]:
        """挂载时的参数，如阈值。"""
        ...

    def run(self, trigger: Trigger, ctx: C) -> None:
        """执行一次。trigger 说明为什么被调用；能做什么只取决于 ctx。抛出的异常由 event 隔离并记日志。"""
        ...
