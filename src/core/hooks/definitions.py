"""钩子的纯数据定义：模板里写的挂载（前端据此生成表单，随模板存库）。编译后的活对象见 mount.py。

只依赖 pydantic，不依赖任何运行时对象。
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# 挂载点是核心结构事实，固定这几个：
#   生命周期 created / closed · 数据进入 pre（不算条件，启发钩子专用）
#   条件命中 rule_hit · 后置 post
MountPoint = Literal["created", "closed", "pre", "rule_hit", "post"]


class MountDef(BaseModel):
    """Mount a hook at one or more places, as written in a template.

    The places are the event's mount points in `at` plus the rule_hit of each rule in
    `rules`. One mount has one state across all of them.
    """

    model_config = ConfigDict(frozen=True)

    hook: str                   # hook name in the HookRegistry
    name: str | None = None     # unique in the template; defaults to the hook name
    at: list[MountPoint] = Field(default_factory=list[MountPoint])   # rule_hit goes in rules
    rules: list[str] = Field(default_factory=list[str])              # rule names, run at rule_hit
    params: dict[str, Any] = Field(default_factory=dict[str, Any])

    @property
    def mount_name(self) -> str:
        """The name the mount's state is kept under."""
        return self.name if self.name is not None else self.hook
