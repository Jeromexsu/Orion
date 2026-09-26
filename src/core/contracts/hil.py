"""hil 契约。Suggestion 是“操作提案”而不是“发现”。"""

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class Proposal(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: str                 # 只能是白名单里的核心公开方法名，如 "add_target"
    target: str | None = None   # 作用对象 ID
    args: dict[str, Any] = Field(default_factory=dict[str, Any])


class Suggestion(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: uuid4().hex)
    source: str                 # 提出建议的算子名
    reason: str                 # 人类可读的理由
    evidence: list[str] = Field(default_factory=list[str])  # 依据的动态数据 source_id
    proposal: Proposal
