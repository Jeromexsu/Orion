from abc import ABC, abstractmethod
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

from core.operators.context import BaseContext
from core.operators.occasion import Occasion

# 四类算子：推进（改状态）/ 输出（报告、通知）/ 发现（启发）/ 校正（校准）
Category = Literal["progress", "output", "discover", "calibrate"]

# 可挂的层级：父事件级、子事件级
Level = Literal["parent", "event"]

# 挂载点是核心结构事实，固定这几个：
#   生命周期 created / closed · 数据进入 pre（不算条件，启发算子专用）
#   条件命中 rule_hit · 状态变更后 status_updated · 后置 post
MountPoint = Literal["created", "closed", "pre", "rule_hit", "status_updated", "post"]

C = TypeVar("C", bound=BaseContext)


class Operator(ABC, Generic[C]):
    """算子基类。具体算子是插件，继承它，放在 plugins/operators/ 下：

        class CountHits(Operator[ProgressContext]):
            name = "count_hits"
            category = "progress"
            levels = frozenset({"event"})
            mount_points = frozenset({"rule_hit"})
            params_model = CountHitsParams

            def run(self, occasion: Occasion, ctx: ProgressContext) -> None: ...

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
    def run(self, occasion: Occasion, ctx: C) -> None:
        """Run once.

        Args:
            occasion: Why it is being run — the mount point and what happened there;
                match on its type to get the fields that mount point always has.
            ctx: What it may do, decided by its category. Exceptions are isolated
                and logged by the event.
        """
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
