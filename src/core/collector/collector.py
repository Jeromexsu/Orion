import logging
from datetime import datetime

from core.collector.registry import UpstreamAdapterRegistry
from core.collector.repository import CursorRepository, ObservationRepository
from core.target import ObservableTarget, ObservationEnvelope, TargetManager

logger = logging.getLogger(__name__)


class Collector:
    """Collects observations for active observable targets from their upstreams.

    For each active upstream of each active observable target: choose a query,
    fetch through the upstream adapter, check the observation class, drop
    duplicates, store, advance the cursor; then publish through the observable
    target. collect() is called periodically by the in-process scheduler.
    """

    def __init__(
        self,
        target_manager: TargetManager,
        upstream_adapter_registry: UpstreamAdapterRegistry,
        cursor_repository: CursorRepository,
        observation_repository: ObservationRepository,
    ) -> None:
        self._target_manager = target_manager
        self._upstream_adapter_registry = upstream_adapter_registry
        self._cursor_repository = cursor_repository
        self._observation_repository = observation_repository

    def collect(self) -> list[ObservationEnvelope]:
        """Run one collection round over all active observable targets.

        Active observable targets (at least one subscriber) are asked from the
        TargetManager; each is collected with collect_one, which stores and
        publishes its new observations. An observable target that raises is logged
        and skipped without affecting the others. Called periodically by the
        in-process scheduler.

        Returns:
            Newly stored envelopes of this round, grouped per observable target.
        """
        collected: list[ObservationEnvelope] = []
        for observable in self._target_manager.active_observables():
            try:
                collected.extend(self.collect_one(observable))
            except Exception:
                logger.exception("collect failed for %s", observable.id)
        return collected

    def collect_one(self, observable: ObservableTarget) -> list[ObservationEnvelope]:
        """Collect new observations of one observable target from its active upstreams.

        Called by collect for every active observable target; also usable on demand
        to collect one observable target immediately (e.g. a manual refresh).

        Active upstreams are those with at least one subscriber. Each is collected
        with its own cursor; an upstream that raises is logged and skipped without
        affecting the others. After all active upstreams are done, the new
        observations are published in occurred_at order through the observable
        target, which delivers each to the subscribers of its upstream.

        Args:
            observable: The observable target to collect for.

        Returns:
            Newly stored envelopes from all active upstreams, sorted by occurred_at.
        """
        new: list[ObservationEnvelope] = []
        for upstream in observable.active_upstreams():
            try:
                new.extend(self._collect_upstream(observable, upstream))
            except Exception:
                logger.exception("upstream %s failed for %s", upstream, observable.id)

        new.sort(key=lambda e: e.occurred_at)
        for envelope in new:
            observable.publish(envelope)
        return new

    def _collect_upstream(
        self, observable: ObservableTarget, upstream: str
    ) -> list[ObservationEnvelope]:
        """Collect new observations of one observable target from one upstream.

        Stores them in the observation repository and advances the cursor of this
        (observable target, upstream) pair. Does not publish: collect_one publishes
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
        target = self._target_manager.get_target(observable.target_id)   # 当前的目标，不是快照
        query = adapter.choose_query(target.query_values())

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
