"""target 模块和 repo 层之间的契约：持久化记录 + 仓库接口（由 persistence 层实现，bootstrap 时注入）。"""

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


class TargetRecord(BaseModel):
    """目标的持久化形态：与具体类型无关，持久化层不需要认识插件。

    按 type 找到对应的 Target 子类，再用它的 from_record 还原。
    """

    model_config = ConfigDict(frozen=True)

    id: str
    type: str
    name: str
    aliases: list[str] = Field(default_factory=list[str])
    attributes: dict[str, Any] = Field(default_factory=dict[str, Any])



class TargetRepository(Protocol):
    """存取与类型无关的 TargetRecord；还原成具体子类由 TargetManager 负责。"""

    def get(self, target_id: str) -> TargetRecord | None:
        """不存在返回 None。"""
        ...

    def upsert(self, target: TargetRecord) -> None:
        """按 id 新建或覆盖。"""
        ...

    def remove(self, target_id: str) -> None:
        """不存在时忽略。"""
        ...

    def find_by_alias(self, alias: str) -> TargetRecord | None:
        """aliases 里含该别名的目标；没有返回 None。"""
        ...
