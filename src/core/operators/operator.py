from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel

from core.operators.context import BaseContext
from core.operators.trigger import Category, Level, MountPoint, Trigger

C = TypeVar("C", bound=BaseContext)


class Operator(ABC, Generic[C]):
    """算子基类。具体算子是插件，继承它，放在 plugins/operators/ 下：

        class CountHits(Operator[ProgressContext]):
            name = "count_hits"
            category = "progress"
            levels = frozenset({"event"})
            mount_points = frozenset({"rule_hit"})
            params_model = CountHitsParams

            def run(self, trigger: Trigger, ctx: ProgressContext) -> None: ...

    类属性的类型在这里声明，子类直接赋值即可。
    category 决定运行时拿到哪种上下文：progress → ProgressContext，
    discover / calibrate → SuggestContext，output → BaseContext。泛型参数 C 应与之一致。
    """

    name: str                           # 模板里按名字引用，发布后不改
    category: Category                  # 算子类别，决定拿到哪种上下文
    levels: frozenset[Level]            # 可以挂在哪些层级（父事件 / 子事件）
    mount_points: frozenset[MountPoint]  # 可以挂在哪些挂载点
    params_model: type[BaseModel]       # 挂载时的参数，如阈值

    @abstractmethod
    def run(self, trigger: Trigger, ctx: C) -> None:
        """执行一次。trigger 说明为什么被调用；能做什么只取决于 ctx。抛出的异常由 event 隔离并记日志。"""
        ...


def check_operator(operator: Operator[C]) -> None:
    """注册时检查子类把类属性都声明了，漏写抛 TypeError。"""
    missing = [
        attr
        for attr in ("name", "category", "levels", "mount_points", "params_model")
        if not hasattr(operator, attr)
    ]
    if missing:
        raise TypeError(f"{type(operator).__name__} must set {', '.join(missing)}")
