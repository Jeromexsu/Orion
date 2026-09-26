"""跨模块数据契约（纯数据、跨 JSON 边界，全部 Pydantic）。

core 里所有模块都可以 import 这里；这里不 import core 的任何其他模块。
模块自己的行为对象和 Protocol 不放这里。
"""

from core.contracts.condition import (
    HIT,
    MISS,
    NOT_APPLICABLE,
    ConditionDef,
    EvalResult,
    LeafDef,
    OpDef,
    Outcome,
)
from core.contracts.data import DynamicData, QuerySpec
from core.contracts.hil import Proposal, Suggestion
from core.contracts.operators import Category, Level, MountPoint, Trigger
from core.contracts.report import DRAFT, EDITING, SENT, Draft, DraftStatus

__all__ = [
    "DRAFT",
    "EDITING",
    "HIT",
    "MISS",
    "NOT_APPLICABLE",
    "SENT",
    "Category",
    "ConditionDef",
    "Draft",
    "DraftStatus",
    "DynamicData",
    "EvalResult",
    "LeafDef",
    "Level",
    "MountPoint",
    "OpDef",
    "Outcome",
    "Proposal",
    "QuerySpec",
    "Suggestion",
    "Trigger",
]
