import logging
from datetime import datetime

from pydantic import ValidationError

from core.collector.dispatcher import Dispatcher
from core.collector.registry import AdapterRegistry
from core.collector.repository import CursorRepository, DynamicDataRepository
from core.target import DynamicData, ObservableTarget, TargetManager

logger = logging.getLogger(__name__)


class Collector:
    """遍历活跃的 ObservableTarget，拉取 → 校验 → 去重 → 落库 → 分发。

    由进程内调度器定时调用 collect()。
    """

    def __init__(
        self,
        targets: TargetManager,
        adapters: AdapterRegistry,
        cursors: CursorRepository,
        data: DynamicDataRepository,
        dispatcher: Dispatcher,
    ) -> None:
        self._targets = targets
        self._adapters = adapters
        self._cursors = cursors
        self._data = data
        self._dispatcher = dispatcher

    def collect(self) -> list[DynamicData]:
        """采集一轮，返回本轮新落库的数据。单个目标或上游失败不影响其他。"""
        collected: list[DynamicData] = []
        for observable in self._targets.active_observables():
            try:
                collected.extend(self.collect_one(observable))
            except Exception:
                logger.exception("collect failed for %s", observable.id)
        return collected

    def collect_one(self, observable: ObservableTarget) -> list[DynamicData]:
        """只拉有人订阅的上游，每个上游用自己的游标。"""
        new: list[DynamicData] = []
        for upstream in observable.active_upstreams():
            try:
                new.extend(self._collect_upstream(observable, upstream))
            except Exception:
                logger.exception("upstream %s failed for %s", upstream, observable.id)

        for data in sorted(new, key=lambda d: d.occurred_at):
            self._dispatcher.dispatch(observable, data)
        return new

    def _collect_upstream(self, observable: ObservableTarget, upstream: str) -> list[DynamicData]:
        cursor = self._cursors.get(observable.id, upstream)
        spec = observable.query_spec(datetime.fromisoformat(cursor) if cursor else None)
        records = self._adapters.get(upstream).fetch(spec)

        new: list[DynamicData] = []
        for record in sorted(records, key=lambda r: r.occurred_at):
            if self._data.exists(record.source_id):
                continue
            try:
                fields = observable.validate_fields(record.fields)
            except ValidationError:
                logger.warning("invalid record %s for %s", record.source_id, observable.id)
                continue
            data = DynamicData(
                observable_id=observable.id,
                upstream=upstream,
                fields=fields,
                occurred_at=record.occurred_at,
                source_id=record.source_id,
                raw=record.raw,
            )
            self._data.append(data)
            new.append(data)

        # 先推进游标再分发：订阅者失败不应导致重复采集
        if new:
            self._cursors.set(observable.id, upstream, max(d.occurred_at for d in new).isoformat())
        return new
