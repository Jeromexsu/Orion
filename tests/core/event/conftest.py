from datetime import UTC, datetime, timedelta
from itertools import count
from typing import Any

import pytest

from core.condition_engine import ConditionCompiler, EvaluatorRegistry
from core.event import EventRuntime, ParentEventManager, ParentEventServices, TemplateCompiler
from core.hil import Proposal
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
from core.report import ReportManager
from core.target import ObservationEnvelope, TargetManager
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


class Log:
    """被测钩子共用的调用记录。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, MountPoint]] = []


@hook(mount_points=ALL_MOUNTS)
class Recorder(Hook[NoParams]):
    """什么都不声明：只记录被调用的挂载点，不影响系统。"""

    def __init__(self, log: Log) -> None:
        self.log = log

    def run(self, occasion: Occasion, ctx: HookContext[NoParams]) -> None:
        self.log.calls.append((self.name, occasion.mount_point))


@hook(mount_points={"status_updated"}, scopes={"event"})
class Echo(Hook[NoParams]):
    """直接作用于子事件，挂在 status_updated：再次 update_status 用来验证不会无限递归。"""

    def run(self, occasion: Occasion, ctx: HookContext[NoParams]) -> None:
        ctx.event.update_status({"echoed": int(ctx.state.get("echoed", 0)) + 1})


@hook(mount_points={"pre"}, proposes=True)
class Spotter(Hook[NoParams]):
    """只提议，挂在 pre：每条数据都提一个提议。"""

    def run(self, occasion: Occasion, ctx: HookContext[NoParams]) -> None:
        assert isinstance(occasion, ObservationOccasion)  # 只挂在 pre：一定是观测到达
        ctx.propose(
            Proposal(
                source=self.name,
                reason=f"saw {ctx.target_name(occasion.envelope.observable_id)}",
                evidence=[occasion.envelope.source_id],
                action="add_target", args={},
            )
        )


@hook(mount_points=ALL_MOUNTS)
class Boom(Hook[NoParams]):
    def run(self, occasion: Occasion, ctx: HookContext[NoParams]) -> None:
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
        self.hook_registry = HookRegistry()
        for hook in (CountHits(), Recorder(self.log), Echo(), Spotter(), Boom(), CloseReport(self.reports)):
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
        self.services = self.make_services(self.targets)
        self.parent_events = ParentEventManager(self.parents, self.services, self.runtime)
        self._seq = count()

    def make_targets(self) -> TargetManager:
        """新的 TargetManager 共用同一个目标仓库——模拟重启时内存状态清空。

        可观测目标仓库每次新建，记在 observable_repo 上，测试据此检查有没有创建可观测目标。
        """
        self.observable_repo = InMemoryObservableTargetRepository()
        targets = TargetManager(
            self.target_repo,
            self.observable_repo,
            StaticUpstreamCatalog({("aircraft", "position"): ["adsb", "radar"]}),
        )
        targets.register_type(Aircraft)
        return targets

    def make_services(self, targets: TargetManager) -> ParentEventServices:
        evaluator_registry = EvaluatorRegistry()
        evaluator_registry.register(OnEnter())
        return ParentEventServices(
            target_manager=targets,
            template_repository=self.templates,
            template_compiler=TemplateCompiler(
                ConditionCompiler(evaluator_registry), MountCompiler(self.hook_registry), targets
            ),
            report_manager=self.reports,
        )

    def make_parent_events(self, targets: TargetManager) -> ParentEventManager:
        """用给定的 TargetManager 组装一套新的父事件管理器——模拟重启（仓库共用）。"""
        return ParentEventManager(self.parents, self.make_services(targets), self.runtime)

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


def mount(hook: str, mount_point: str, **params: Any) -> dict[str, Any]:
    return {"hook": hook, "mount_point": mount_point, "params": params}


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
                "mount_defs": [mount("countHits", "rule_hit", threshold=threshold)],
            }
        ],
        "mount_defs": mounts or [],
    }


@pytest.fixture
def env() -> Env:
    return Env()
