import builtins
from abc import ABC, abstractmethod
from collections.abc import Mapping, Set
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from core.condition_engine.resolver import Observation
from core.contracts import EvalResult

P = TypeVar("P", bound=BaseModel)


class Evaluator(ABC, Generic[P]):
    """一种判断方式（叶子条件）。每种一个实现，放在 plugins/condition_engine/ 下。

    规则：
    - 不得修改传入的 obs 和 state（传进来的是只读视图）；新状态通过 state_patch 返回；
    - 返回“不适用”时不得产出 state_patch。
    """

    type: str                   # 模板里引用的名字，如 "onEnter"
    requires: Set[str]          # 需要的动态数据字段
    params_model: builtins.type[P]  # 类体里的 type 属性遮蔽了内置 type

    @abstractmethod
    def evaluate(self, params: P, obs: Observation, state: Mapping[str, Any]) -> EvalResult:
        """params：模板里配置、编译时已解析的参数；
        obs：这一条观测（只读），obs.fields 已保证包含 requires，obs.occurred_at 是发生时间；
        state：本叶子上次保存的状态（首次为空），可存任意内容（如滑动窗口），需自行控制大小。
        """
        ...
