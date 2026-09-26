import builtins
from abc import ABC, abstractmethod
from collections.abc import Mapping, Set
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from core.condition_engine.contracts import EvalResult

P = TypeVar("P", bound=BaseModel)


class LeafEvaluator(ABC, Generic[P]):
    """一种判断方式（叶子条件）。每种一个实现，放在 plugins/condition_engine/ 下。

    规则：
    - 不得修改传入的 state（传进来的是只读视图）；新状态通过 state_patch 返回；
    - 返回“不适用”时不得产出 state_patch。
    """

    type: str                   # 模板里引用的名字，如 "onEnter"
    requires: Set[str]          # 需要的动态数据字段
    params_model: builtins.type[P]  # 类体里的 type 属性遮蔽了内置 type

    @abstractmethod
    def evaluate(
        self, params: P, fields: Mapping[str, Any], state: Mapping[str, Any]
    ) -> EvalResult:
        """fields 已保证包含 requires；state 是本叶子上次保存的状态（首次为空）。"""
        ...
