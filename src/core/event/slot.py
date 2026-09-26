from collections.abc import Callable, Mapping

from core.contracts import DynamicData
from core.event.instance import SubEventInstance
from core.event.records import InstanceRecord
from core.event.runtime import EventRuntime
from core.event.template import SubEventTemplate


class SubEventSlot:
    """一个模板一个槽：持有模板 + 当前唯一活跃的实例。

    实例收敛关闭后，下一条相关数据到来时再开新实例。
    """

    def __init__(
        self,
        parent_id: str,
        template: SubEventTemplate,
        runtime: EventRuntime,
        target_names: Callable[[], Mapping[str, str]],
        active: SubEventInstance | None = None,
    ) -> None:
        self._parent_id = parent_id
        self._template = template
        self._runtime = runtime
        self._target_names = target_names
        self._active = active

    @property
    def template(self) -> SubEventTemplate:
        return self._template

    @property
    def active(self) -> SubEventInstance | None:
        return self._active

    def on_data(self, data: DynamicData) -> None:
        if data.observable_id not in self._template.targets:
            return
        instance = self._active or self._open()
        instance.process(data)
        self._runtime.instances.save(instance.to_record())
        self._active = None if instance.is_closed else instance

    def replace(self, template: SubEventTemplate) -> None:
        """换成新版本模板：关掉当前实例，后续数据用新模板开新实例。"""
        self.close_active("template_replaced")
        self._template = template

    def close_active(self, reason: str) -> None:
        if self._active is None:
            return
        self._active.close(reason)
        self._runtime.instances.save(self._active.to_record())
        self._active = None

    def history(self) -> list[InstanceRecord]:
        return self._runtime.instances.history(self._parent_id, self._template.id)

    def _open(self) -> SubEventInstance:
        instance = SubEventInstance.open(
            self._parent_id, self._template, self._runtime, self._target_names
        )
        self._runtime.instances.save(instance.to_record())
        return instance
