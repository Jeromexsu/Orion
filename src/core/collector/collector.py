import logging
from datetime import datetime

from core.collector.dispatcher import Dispatcher
from core.collector.registry import UpstreamAdapterRegistry
from core.collector.repository import CursorRepository, ObservationRepository
from core.target import ObservableTarget, ObservationEnvelope, TargetManager

logger = logging.getLogger(__name__)


class Collector:
    """遍历活跃的 ObservableTarget，拉取 → 校验 → 去重 → 落库 → 分发。

    由进程内调度器定时调用 collect()。
    """

    def __init__(
        self,
        target_manager: TargetManager,
        upstream_adapter_registry: UpstreamAdapterRegistry,
        cursor_repository: CursorRepository,
        observation_repository: ObservationRepository,
        dispatcher: Dispatcher,
    ) -> None:
        self._target_manager = target_manager
        self._upstream_adapter_registry = upstream_adapter_registry
        self._cursor_repository = cursor_repository
        self._observation_repository = observation_repository
        self._dispatcher = dispatcher

    def collect(self) -> list[ObservationEnvelope]:
        """对所有活跃的可观测目标采集一轮，返回本轮新落库的观测。

        写观测库、推进游标、分发给订阅者。单个目标或上游失败只记日志，不影响其他。
        """
        collected: list[ObservationEnvelope] = []
        for observable in self._target_manager.active_observables():
            try:
                collected.extend(self.collect_one(observable))
            except Exception:
                logger.exception("collect failed for %s", observable.id)
        return collected

    def collect_one(self, observable: ObservableTarget) -> list[ObservationEnvelope]:
        """采集一个可观测目标，返回新落库的观测。

        只拉有人订阅的上游，每个上游用自己的游标；全部上游拉完后按发生时间排序再分发。
        """
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
        """Collect new observations of one observable target from one upstream.

        Stores them in the observation repository and advances the cursor of this
        (observable target, upstream) pair. Does not dispatch: collect_one dispatches
        once all upstreams of the observable target are done. Skips records already
        stored (same source_id) and records whose observation does not match the
        observable target's observed point.

        Args:
            observable: The observable target to collect for.
            upstream: Name of the upstream adapter to query.

        Returns:
            Newly stored envelopes, sorted by occurred_at. Empty if the target of
            this observable target no longer provides the query keys of any query
            way of this upstream (e.g. after the target record was updated).
        """
        # get upstream adapter
        adapter = self._upstream_adapter_registry.get(upstream)

        # build query based on target fields required by upstream adapter
        query = adapter.choose_query(observable.target.query_values())

        # target fields not satisfied upstream adapter requirement
        if query is None:
            # 目标记录更新后可能不再满足这个上游的任何查询方式
            logger.warning("%s no longer satisfies any query of %s", observable.id, upstream)
            return []

        # build datetime cursor
        cursor = self._cursor_repository.get(observable.id, upstream)
        since = datetime.fromisoformat(cursor) if cursor else None

        # fetch from upstream
        records = adapter.fetch(observable.observed_point, query, since)

        # convert raw records into observation envelopes
        new: list[ObservationEnvelope] = []
        for record in sorted(records, key=lambda r: r.occurred_at):
            if self._observation_repository.exists(record.source_id):
                continue
            if not observable.accepts(record.observation):
                logger.warning(
                    "%s returned %s for %s, expected %s",
                    upstream,
                    type(record.observation).__name__,
                    observable.id,
                    observable.observed_point.observation.__name__,
                )
                continue
            envelope = ObservationEnvelope(
                observable_id=observable.id,
                upstream=upstream,
                observation=record.observation,
                occurred_at=record.occurred_at,
                source_id=record.source_id,
                raw=record.raw,
            )
            self._observation_repository.append(envelope)
            new.append(envelope)

        # 先推进游标再分发：订阅者失败不应导致重复采集
        if new:
            latest = max(e.occurred_at for e in new)
            self._cursor_repository.set(observable.id, upstream, latest.isoformat())
        return new
