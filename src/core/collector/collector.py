import logging
from datetime import datetime

from pydantic import ValidationError

from core.collector.dispatcher import Dispatcher
from core.collector.registry import AdapterRegistry
from core.collector.repository import CursorRepository, ObservationRepository
from core.target import ObservableTarget, Observation, TargetManager

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

    def collect(self) -> list[Observation]:
        """采集一轮，返回本轮新落库的数据。单个目标或上游失败不影响其他。"""
        collected: list[Observation] = []
        for observable in self._targets.active_observables():
            try:
                collected.extend(self.collect_one(observable))
            except Exception:
                logger.exception("collect failed for %s", observable.id)
        return collected

    def collect_one(self, observable: ObservableTarget) -> list[Observation]:
        """只拉有人订阅的上游，每个上游用自己的游标。"""
        new: list[Observation] = []
        for upstream in observable.active_upstreams():
            try:
                new.extend(self._collect_upstream(observable, upstream))
            except Exception:
                logger.exception("upstream %s failed for %s", upstream, observable.id)

        for observation in sorted(new, key=lambda o: o.occurred_at):
            self._dispatcher.dispatch(observable, observation)
        return new

    def _collect_upstream(self, observable: ObservableTarget, upstream: str) -> list[Observation]:
        cursor = self._cursors.get(observable.id, upstream)
        spec = observable.query_spec(datetime.fromisoformat(cursor) if cursor else None)
        records = self._adapter_registry.get(upstream).fetch(spec)

        new: list[Observation] = []
        for record in sorted(records, key=lambda r: r.occurred_at):
            if self._observations.exists(record.source_id):
                continue
            try:
                fields = observable.validate_fields(record.fields)
            except ValidationError:
                logger.warning("invalid record %s for %s", record.source_id, observable.id)
                continue
            observation = Observation(
                observable_id=observable.id,
                upstream=upstream,
                fields=fields,
                occurred_at=record.occurred_at,
                source_id=record.source_id,
                raw=record.raw,
            )
            self._observations.append(observation)
            new.append(observation)

        # 先推进游标再分发：订阅者失败不应导致重复采集
        if new:
            self._cursors.set(observable.id, upstream, max(d.occurred_at for d in new).isoformat())
        return new
