import builtins
from abc import ABC, abstractmethod
from collections.abc import Mapping, Set
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from core.condition_engine.result import EvalResult
from core.target import ObservationEnvelope

P = TypeVar("P", bound=BaseModel)


class Evaluator(ABC, Generic[P]):
    """一种判断方式（叶子条件）。每种一个实现，放在 plugins/condition_engine/ 下。

    规则：
    - 不得修改传入的 state（只读视图）；新状态通过 state_patch 返回；envelope 是副本；
    - 返回“不适用”时不得产出 state_patch。
    """

    type: str                   # 模板里引用的名字，如 "onEnter"
    requires: Set[str]          # 需要观测里有值的字段（按字段名，不绑定具体观测类型）
    params_model: builtins.type[P]  # 类体里的 type 属性遮蔽了内置 type

    @abstractmethod
    def evaluate(
        self, params: P, envelope: ObservationEnvelope, state: Mapping[str, Any]
    ) -> EvalResult:
        """params：模板里配置、编译时已解析的参数；
        envelope：这一条观测的外壳（副本）。envelope.observation 是观测，requires 里的字段已保证有值，
        按字段名读取（getattr(envelope.observation, "lat")）；envelope.occurred_at 是发生时间；
        判断方式不应依赖 upstream / source_id / raw；
        state：本叶子上次保存的状态（首次为空），可存任意内容（如滑动窗口），需自行控制大小。
        """
        ...
