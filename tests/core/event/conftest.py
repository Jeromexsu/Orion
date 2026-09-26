from datetime import UTC, datetime, timedelta
from itertools import count
from typing import Any

import pytest
from pydantic import BaseModel

from core.condition_engine import ConditionEngine, EvaluatorRegistry
from core.contracts import Category, DynamicData, Level, MountPoint, Proposal, Suggestion, Trigger
from core.event import EventManager, EventRuntime
from core.operators import BaseContext, OperatorRegistry, ProgressContext, SuggestContext
from core.report import ReportManager
from core.target import TargetManager
from plugins.condition_engine.on_enter import OnEnter
from plugins.operators.close_report import CloseReport
from plugins.operators.count_hits import CountHits
from plugins.target.aircraft import Aircraft
from tests.core.event.fakes import (
    InMemoryInstanceRepository,
    InMemoryParentEventRepository,
    InMemorySlotStateRepository,
    InMemoryTemplateRepository,
    RecordingSink,
)
from tests.core.report.fakes import InMemoryDraftRepository
from tests.core.target.fakes import (
    InMemoryObservableTargetRepository,
    InMemoryTargetRepository,
    StaticUpstreamCatalog,
)

SQUARE = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)]
ALL_MOUNTS: frozenset[MountPoint] = frozenset(
    {"created", "closed", "pre", "rule_hit", "status_updated", "post"}
)


class NoParams(BaseModel):
    pass


class Log:
    """被测算子共用的调用记录。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, MountPoint]] = []


class Recorder:
    """输出类：只记录被调用的挂载点。"""

    name = "recorder"
    category: Category = "output"
    levels: frozenset[Level] = frozenset({"instance"})
    mount_points = ALL_MOUNTS
    params_model = NoParams

    def __init__(self, log: Log) -> None:
        self.log = log

    def run(self, trigger: Trigger, ctx: BaseContext) -> None:
        self.log.calls.append((self.name, trigger.mount_point))


class Echo:
    """推进类，挂在 status_updated：再次 update_status 用来验证不会无限递归。"""

    name = "echo"
    category: Category = "progress"
    levels: frozenset[Level] = frozenset({"instance"})
    mount_points: frozenset[MountPoint] = frozenset({"status_updated"})
    params_model = NoParams

    def run(self, trigger: Trigger, ctx: ProgressContext) -> None:
        ctx.update_status({"echoed": int(ctx.state.get("echoed", 0)) + 1})


class Spotter:
    """发现类，挂在 pre：每条数据都提一个建议。"""

    name = "spotter"
    category: Category = "discover"
    levels: frozenset[Level] = frozenset({"instance"})
    mount_points: frozenset[MountPoint] = frozenset({"pre"})
    params_model = NoParams

    def run(self, trigger: Trigger, ctx: SuggestContext) -> None:
        assert trigger.data is not None
        ctx.suggest(
            Suggestion(
                source=self.name,
                reason=f"saw {ctx.target_name(trigger.data.observable_id)}",
                evidence=[trigger.data.source_id],
                proposal=Proposal(action="add_target", args={}),
            )
        )


class Boom:
    name = "boom"
    category: Category = "output"
    levels: frozenset[Level] = frozenset({"instance"})
    mount_points = ALL_MOUNTS
    params_model = NoParams

    def run(self, trigger: Trigger, ctx: BaseContext) -> None:
        raise RuntimeError("boom")


class Env:
    def __init__(self) -> None:
        self.target_repo = InMemoryTargetRepository()
        self.targets = self.make_targets()
        for tid, name in (("t1", "MU5101"), ("t2", "CA1501")):
            self.targets.upsert_target(Aircraft(id=tid, name=name, registration=tid))

        self.log = Log()
        self.drafts = InMemoryDraftRepository()
        self.reports = ReportManager(self.drafts)
        self.operators = OperatorRegistry()
        for op in (CountHits(), Recorder(self.log), Echo(), Spotter(), Boom(), CloseReport(self.reports)):
            self.operators.register(op)

        self.sink = RecordingSink()
        self.parents = InMemoryParentEventRepository()
        self.templates = InMemoryTemplateRepository()
        self.instances = InMemoryInstanceRepository()
        self.slot_states = InMemorySlotStateRepository()
        self.runtime = self.make_runtime(self.targets)
        self.events = EventManager(self.runtime)
        self._seq = count()

    def make_targets(self) -> TargetManager:
        """新的 TargetManager 共用同一个目标仓库——模拟重启时内存状态清空。"""
        targets = TargetManager(
            self.target_repo,
            InMemoryObservableTargetRepository(),
            StaticUpstreamCatalog({("aircraft", "position"): ["adsb", "radar"]}),
        )
        targets.register_type(Aircraft)
        return targets

    def make_runtime(self, targets: TargetManager) -> EventRuntime:
        evaluators = EvaluatorRegistry()
        evaluators.register(OnEnter())
        return EventRuntime(
            targets=targets,
            conditions=ConditionEngine(evaluators, targets),
            operators=self.operators,
            suggestions=self.sink,
            parents=self.parents,
            templates=self.templates,
            instances=self.instances,
            slot_states=self.slot_states,
            reports=self.reports,
        )

    def data(
        self,
        lat: float,
        lon: float,
        observable_id: str = "t1:position",
        upstream: str = "adsb",
    ) -> DynamicData:
        n = next(self._seq)
        return DynamicData(
            observable_id=observable_id,
            upstream=upstream,
            fields={"lat": lat, "lon": lon, "altitude_m": None},
            occurred_at=datetime(2026, 9, 26, tzinfo=UTC) + timedelta(minutes=n),
            source_id=f"adsb#{n}",
        )


def mount(operator: str, mount_point: str, **params: Any) -> dict[str, Any]:
    return {"operator": operator, "mount_point": mount_point, "params": params}


def enter(target: str = "t1:position", initial: bool = False) -> dict[str, Any]:
    return {
        "kind": "leaf",
        "target": target,
        "type": "onEnter",
        "params": {"area": SQUARE, "initial_as_enter": initial},
    }


def template(
    version: int = 1,
    threshold: int = 2,
    target: str = "t1",
    upstreams: list[str] | None = None,
    hooks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """开启条件：目标进入区域；规则：在区域内（开启那一条也算）累计命中，达到阈值收敛关闭。"""
    observable = f"{target}:position"
    return {
        "id": "enter-zone",
        "version": version,
        "name": "进入区域",
        "observations": [
            {"target_id": target, "focus": "position", "upstreams": upstreams or ["adsb"]}
        ],
        "open_condition": enter(observable),
        "rules": [
            {
                "name": "enter",
                "condition": enter(observable, initial=True),
                "hooks": [mount("count_hits", "rule_hit", threshold=threshold)],
            }
        ],
        "hooks": hooks or [],
    }


@pytest.fixture
def env() -> Env:
    return Env()
