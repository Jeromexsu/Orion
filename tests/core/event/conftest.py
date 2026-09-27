from datetime import UTC, datetime, timedelta
from itertools import count
from typing import Any

import pytest

from core.condition_engine import ConditionCompiler, EvaluatorRegistry
from core.event import EventRuntime, ParentEventManager, ParentEventServices, TemplateCompiler
from core.hooks import (
    Hook,
    HookContext,
    HookRegistry,
    MountCompiler,
    MountPoint,
    NoParams,
    ObservationOccasion,
    Occasion,
    hook,
)
from core.observable import ObservableTargetFactory
from core.observation import ObservationEnvelope
from core.report import ReportManager
from core.target import TargetManager, TargetTypeRegistry
from plugins.condition_engine.on_enter import OnEnter
from plugins.hooks.close_report import CloseReport
from plugins.hooks.count_hits import CountHits
from plugins.observed_points.position import PositionObservation
from plugins.target.aircraft import Aircraft
from tests.core.event.fakes import (
    InMemoryEventRepository,
    InMemoryParentEventRepository,
    InMemoryRunnerStateRepository,
    InMemoryTemplateRepository,
    RecordingSink,
    StaticUpstreamCatalog,
)
from tests.core.report.fakes import InMemoryReportRepository
from tests.core.target.fakes import InMemoryTargetRepository

SQUARE = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)]
ALL_MOUNTS: frozenset[MountPoint] = frozenset(
    {"created", "closed", "pre", "rule_hit", "post"}
)


class Log:
    """被测钩子共用的调用记录。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, MountPoint]] = []


@hook(mount_points=ALL_MOUNTS)
class Recorder(Hook[NoParams]):
    """什么都不声明：只记录被调用的挂载点，不影响系统。"""

    def __init__(self, log: Log) -> None:
        self.log = log

    def run(self, params: NoParams, ctx: HookContext, occasion: Occasion) -> None:
        self.log.calls.append((self.name, occasion.mount_point))


@hook(mount_points={"pre"}, proposes=True)
class Spotter(Hook[NoParams]):
    """只提议，挂在 pre：每条数据都提一个提议。"""

    def run(self, params: NoParams, ctx: HookContext, occasion: Occasion) -> None:
        assert isinstance(occasion, ObservationOccasion)  # 只挂在 pre：一定是观测到达
        ctx.propose(
            "add_target",
            {"parent_id": ctx.parent_id, "target_id": "t2"},
            reason=f"saw {ctx.target_name(occasion.envelope.observable_id)}",
            evidence=[occasion.envelope.source_id],
        )


@hook(mount_points=ALL_MOUNTS)
class Boom(Hook[NoParams]):
    def run(self, params: NoParams, ctx: HookContext, occasion: Occasion) -> None:
        raise RuntimeError("boom")


class Env:
    def __init__(self) -> None:
        self.target_repo = InMemoryTargetRepository()
        self.targets, self.observables = self.make_targets()
        for tid, name in (("t1", "MU5101"), ("t2", "CA1501")):
            self.targets.upsert_target(Aircraft(id=tid, name=name, registration=tid))

        self.log = Log()
        self.report_repo = InMemoryReportRepository()
        self.reports = ReportManager(self.report_repo)
        self.hook_registry = HookRegistry()
        for hook in (CountHits(), Recorder(self.log), Spotter(), Boom(), CloseReport(self.reports)):
            self.hook_registry.register(hook)

        self.sink = RecordingSink()
        self.parents = InMemoryParentEventRepository()
        self.templates = InMemoryTemplateRepository()
        self.events = InMemoryEventRepository()
        self.runner_states = InMemoryRunnerStateRepository()
        self.runtime = EventRuntime(
            event_repository=self.events,
            runner_state_repository=self.runner_states,
            proposal_sink=self.sink,
        )
        self.services = self.make_services(self.targets, self.observables)
        self.parent_events = ParentEventManager(self.parents, self.services, self.runtime)
        self._seq = count()

    def make_targets(self) -> tuple[TargetManager, ObservableTargetFactory]:
        """新的 TargetManager / ObservableTargetFactory 共用同一个目标仓库——模拟重启时内存状态清空。"""
        target_types = TargetTypeRegistry()
        target_types.register(Aircraft)
        targets = TargetManager(target_types, self.target_repo)
        observables = ObservableTargetFactory(targets)
        return targets, observables

    def make_services(
        self, targets: TargetManager, observables: ObservableTargetFactory
    ) -> ParentEventServices:
        evaluator_registry = EvaluatorRegistry()
        evaluator_registry.register(OnEnter())
        return ParentEventServices(
            target_manager=targets,
            template_repository=self.templates,
            template_compiler=TemplateCompiler(
                ConditionCompiler(evaluator_registry),
                MountCompiler(self.hook_registry),
                targets,
                StaticUpstreamCatalog({("aircraft", "position"): ["adsb", "radar"]}),
                observables,
            ),
            report_manager=self.reports,
        )

    def make_parent_events(
        self, targets: TargetManager, observables: ObservableTargetFactory
    ) -> ParentEventManager:
        """用给定的两个 manager 组装一套新的父事件管理器——模拟重启（仓库共用）。"""
        return ParentEventManager(
            self.parents, self.make_services(targets, observables), self.runtime
        )

    def envelope(
        self,
        lat: float,
        lon: float,
        observable_id: str = "t1:position",
        upstream: str = "adsb",
    ) -> ObservationEnvelope:
        n = next(self._seq)
        return ObservationEnvelope(
            observable_id=observable_id,
            upstream=upstream,
            observation=PositionObservation(lat=lat, lon=lon),
            occurred_at=datetime(2026, 9, 26, tzinfo=UTC) + timedelta(minutes=n),
            source_id=f"adsb#{n}",
        )


def mount(
    hook: str, *at: str, rules: list[str] | None = None, name: str | None = None, **params: Any
) -> dict[str, Any]:
    """A MountDef as JSON: mounted at the mount points in at and on the rules in rules."""
    raw: dict[str, Any] = {"hook": hook, "at": list(at), "rules": rules or [], "params": params}
    if name is not None:
        raw["name"] = name
    return raw


def enter(observable: str = "t1:position", initial: bool = False) -> dict[str, Any]:
    return {
        "kind": "leaf",
        "observable": observable,
        "op": "onEnter",
        "criteria": {"area": SQUARE, "initial_as_enter": initial},
    }


def template(
    version: int = 1,
    threshold: int = 2,
    target: str = "t1",
    upstreams: list[str] | None = None,
    mounts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """开启条件：目标进入区域；规则：在区域内（开启那一条也算）累计命中，达到阈值收敛关闭。"""
    observable = f"{target}:position"
    return {
        "id": "enter-zone",
        "version": version,
        "name": "进入区域",
        "observable_defs": [
            {"target_id": target, "observed_point": "position", "upstreams": upstreams or ["adsb"]}
        ],
        "open_condition_def": enter(observable),
        "rule_defs": [
            {
                "name": "enter",
                "condition_def": enter(observable, initial=True),
            }
        ],
        "mount_defs": [mount("countHits", rules=["enter"], threshold=threshold), *(mounts or [])],
    }


@pytest.fixture
def env() -> Env:
    return Env()
