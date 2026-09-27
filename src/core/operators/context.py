"""三种上下文，按最小权限给算子：运行时拿到的对象真的没有越权的方法。"""

from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from core.hil import Suggestion

if TYPE_CHECKING:  # operator.py imports this module, so import Category for typing only
    from core.operators.operator import Category


class BaseContext(BaseModel):
    """只读上下文，输出类用。可随异步算子序列化进队列。"""

    model_config = ConfigDict(frozen=True)

    state: dict[str, Any]       # 子事件状态的副本，改了也不影响子事件
    params: dict[str, Any]      # 挂载时的参数
    target_names: dict[str, str] = Field(default_factory=dict[str, str])
    parent_id: str | None = None        # 算子挂在哪个父事件 / 子事件上，报告类算子写草稿时用
    event_id: str | None = None

    def target_name(self, observable_id: str) -> str:
        """目标展示名，报告类算子用。未知时退回 ID。"""
        return self.target_names.get(observable_id, observable_id)


class ProgressContext(BaseContext):
    """+update_status，推进（收敛）类用。必须同步执行：它改的是内存里的活对象。"""

    _update_status: Callable[[dict[str, Any]], None] = PrivateAttr()

    def __init__(self, *, update_status: Callable[[dict[str, Any]], None], **data: Any) -> None:
        super().__init__(**data)
        self._update_status = update_status

    def update_status(self, patch: dict[str, Any]) -> None:
        """把 patch 合并进子事件状态（写库），随后触发 status_updated 钩子。"""
        self._update_status(patch)


class SuggestContext(BaseContext):
    """+suggest，发现/校正类用。"""

    _suggest: Callable[[Suggestion], None] = PrivateAttr()

    def __init__(self, *, suggest: Callable[[Suggestion], None], **data: Any) -> None:
        super().__init__(**data)
        self._suggest = suggest

    def suggest(self, item: Suggestion) -> None:
        """提交一条建议给 hil，等分析师确认；不直接改任何东西。"""
        self._suggest(item)


def build_context(
    category: "Category",
    *,
    state: Mapping[str, Any],
    params: Mapping[str, Any],
    target_names: Mapping[str, str],
    update_status: Callable[[dict[str, Any]], None],
    suggest: Callable[[Suggestion], None],
    parent_id: str | None = None,
    event_id: str | None = None,
) -> BaseContext:
    """event 侧按算子类别构造对应的上下文：ctx = build_context(op.category, ...); op.run(occasion, ctx)。"""
    common: dict[str, Any] = {
        "state": deepcopy(dict(state)),
        "params": deepcopy(dict(params)),
        "target_names": dict(target_names),
        "parent_id": parent_id,
        "event_id": event_id,
    }
    match category:
        case "progress":
            return ProgressContext(update_status=update_status, **common)
        case "discover" | "calibrate":
            return SuggestContext(suggest=suggest, **common)
        case "output":
            return BaseContext(**common)
