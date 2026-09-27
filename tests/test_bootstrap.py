from typing import Any

import pytest

from bootstrap import App, Repositories, build_app
from core.hil import InvalidProposalArgsError, Proposal, ProposalOrigin
from core.target import TargetNotFoundError, type_name
from plugins.target.aircraft import Aircraft
from tests.core.collector.fakes import InMemoryCursorRepository, InMemoryObservationRepository
from tests.core.event.fakes import (
    InMemoryEventRepository,
    InMemoryParentEventRepository,
    InMemoryRunnerStateRepository,
    InMemoryTemplateRepository,
)
from tests.core.hil.fakes import InMemoryProposalRepository
from tests.core.report.fakes import InMemoryReportRepository
from tests.core.target.fakes import InMemoryTargetRepository


def build() -> App:
    return build_app(
        Repositories(
            target_repository=InMemoryTargetRepository(),
            cursor_repository=InMemoryCursorRepository(),
            observation_repository=InMemoryObservationRepository(),
            parent_event_repository=InMemoryParentEventRepository(),
            template_repository=InMemoryTemplateRepository(),
            event_repository=InMemoryEventRepository(),
            runner_state_repository=InMemoryRunnerStateRepository(),
            report_repository=InMemoryReportRepository(),
            proposal_repository=InMemoryProposalRepository(),
        )
    )


def test_build_app_wires_everything() -> None:
    app = build()
    assert [type_name(t) for t in app.target_type_registry.types()] == ["aircraft"]
    assert [o.name for o in app.hook_registry.hooks()] == ["countHits", "closeReport"]
    assert app.hil_manager.allowed_actions() == ["add_target", "remove_target", "upsert_template"]
    assert app.parent_event_manager.parents() == []


def test_accepted_proposal_goes_through_public_method() -> None:
    app = build()
    app.target_manager.upsert_target(Aircraft(id="t1", name="MU5101", registration="B-2447"))
    app.parent_event_manager.create("p1", "东海方向")

    origin = ProposalOrigin(hook="aliasFinder", mount="aliasFinder", parent_id="p1", event_id="e1")

    def propose(**args: Any) -> Proposal:
        p = Proposal(origin=origin, action="add_target", args=args, reason="x")
        app.hil_manager.receive(p)
        return p

    # 参数不合动作的模型 → 进不了审核队列
    with pytest.raises(InvalidProposalArgsError):
        propose(target_id="t1")

    # 目标不存在 → 公开方法的校验照常生效，提议保持待审
    bad = propose(parent_id="p1", target_id="ghost")
    with pytest.raises(TargetNotFoundError):
        app.hil_manager.accept(bad.id)
    assert app.hil_manager.pending() == [bad]

    good = propose(parent_id="p1", target_id="t1")
    app.hil_manager.accept(good.id)
    assert app.parent_event_manager.get("p1").target_ids() == {"t1"}
