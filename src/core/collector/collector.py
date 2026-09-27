import logging
from datetime import datetime

from pydantic import ValidationError

from core.collector.dispatcher import Dispatcher
from core.collector.registry import AdapterRegistry, match_query_fields
from core.collector.repository import CursorRepository, ObservationRepository
from core.target import ObservableTarget, ObservationEnvelope, TargetManager

logger = logging.getLogger(__name__)


class Collector:
    """遍历活跃的 ObservableTarget，拉取 → 校验 → 去重 → 落库 → 分发。

    由进程内调度器定时调用 collect()。
    """

    def __init__(
        self,
        targets: TargetManager,
        adapter_registry: AdapterRegistry,
        cursors: CursorRepository,
        observations: ObservationRepository,
        dispatcher: Dispatcher,
    ) -> None:
        self._targets = targets
        self._adapter_registry = adapter_registry
        self._cursors = cursors
        self._observations = observations
        self._dispatcher = dispatcher

    def collect(self) -> list[ObservationEnvelope]:
        """采集一轮，返回本轮新落库的数据。单个目标或上游失败不影响其他。"""
        collected: list[ObservationEnvelope] = []
        for observable in self._targets.active_observables():
            try:
                collected.extend(self.collect_one(observable))
            except Exception:
                logger.exception("collect failed for %s", observable.id)
        return collected

    def collect_one(self, observable: ObservableTarget) -> list[ObservationEnvelope]:
        """只拉有人订阅的上游，每个上游用自己的游标。"""
        new: list[ObservationEnvelope] = []
        for upstream in observable.active_upstreams():
            try:
                new.extend(self._collect_upstream(observable, upstream))
            except Exception:
                logger.exception("upstream %s failed for %s", upstream, observable.id)

        for envelope in sorted(new, key=lambda e: e.occurred_at):
            self._dispatcher.dispatch(observable, envelope)
        return new

    def _collect_upstream(
        self, observable: ObservableTarget, upstream: str
    ) -> list[ObservationEnvelope]:
        adapter = self._adapter_registry.get(upstream)
        query_fields = match_query_fields(adapter, observable.target)
        if query_fields is None:
            # 目标记录更新后可能不再满足这个上游的任何查询方式
            logger.warning("%s no longer satisfies any query of %s", observable.id, upstream)
            return []
        cursor = self._cursors.get(observable.id, upstream)
        since = datetime.fromisoformat(cursor) if cursor else None
        spec = observable.query_spec(query_fields, since)
        records = adapter.fetch(spec)

        new: list[ObservationEnvelope] = []
        for record in sorted(records, key=lambda r: r.occurred_at):
            if self._observations.exists(record.source_id):
                continue
            try:
                observation = observable.parse_observation(record.fields)
            except ValidationError:
                logger.warning("invalid record %s for %s", record.source_id, observable.id)
                continue
            envelope = ObservationEnvelope(
                observable_id=observable.id,
                upstream=upstream,
                observation=observation,
                occurred_at=record.occurred_at,
                source_id=record.source_id,
                raw=record.raw,
            )
            self._observations.append(envelope)
            new.append(envelope)

        # 先推进游标再分发：订阅者失败不应导致重复采集
        if new:
            self._cursors.set(observable.id, upstream, max(e.occurred_at for e in new).isoformat())
        return new
