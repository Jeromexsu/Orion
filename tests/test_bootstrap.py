from typing import Any

import pytest

from bootstrap import App, Repositories, build_app
from core.hil import Proposal, Suggestion
from core.target import TargetNotFoundError, type_name
from plugins.target.aircraft import Aircraft
from tests.core.collector.fakes import InMemoryCursorRepository, InMemoryObservationRepository
from tests.core.event.fakes import (
    InMemoryEventRepository,
    InMemoryParentEventRepository,
    InMemoryRunnerStateRepository,
    InMemoryTemplateRepository,
)
from tests.core.hil.fakes import InMemorySuggestionRepository
from tests.core.report.fakes import InMemoryDraftRepository
from tests.core.target.fakes import InMemoryObservableTargetRepository, InMemoryTargetRepository


def build() -> App:
    return build_app(
        Repositories(
            target_repository=InMemoryTargetRepository(),
            observable_target_repository=InMemoryObservableTargetRepository(),
            cursor_repository=InMemoryCursorRepository(),
            observation_repository=InMemoryObservationRepository(),
            parent_event_repository=InMemoryParentEventRepository(),
            template_repository=InMemoryTemplateRepository(),
            event_repository=InMemoryEventRepository(),
            runner_state_repository=InMemoryRunnerStateRepository(),
            draft_repository=InMemoryDraftRepository(),
            suggestion_repository=InMemorySuggestionRepository(),
        )
    )


def test_build_app_wires_everything() -> None:
    app = build()
    assert [type_name(t) for t in app.target_manager.types()] == ["aircraft"]
    assert [o.name for o in app.operator_registry.operators()] == ["count_hits", "close_report"]
    assert app.hil_manager.allowed_actions() == ["add_target", "remove_target", "upsert_template"]
    assert app.parent_event_manager.get_pevents() == []


def test_accepted_suggestion_goes_through_public_method() -> None:
    app = build()
    app.target_manager.upsert_target(Aircraft(id="t1", name="MU5101", registration="B-2447"))
    app.parent_event_manager.create("p1", "东海方向")

    def propose(**args: Any) -> Suggestion:
        s = Suggestion(
            source="alias_finder",
            reason="x",
            proposal=Proposal(action="add_target", target="p1", args=args),
        )
        app.hil_manager.receive(s)
        return s

    # 目标不存在 → 公开方法的校验照常生效，建议保持待审
    bad = propose(target_id="ghost")
    with pytest.raises(TargetNotFoundError):
        app.hil_manager.accept(bad.id)
    assert app.hil_manager.pending() == [bad]

    good = propose(target_id="t1")
    app.hil_manager.accept(good.id)
    assert app.parent_event_manager.get_pevent_by_id("p1").target_ids() == {"t1"}
