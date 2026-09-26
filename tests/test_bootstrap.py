from typing import Any

import pytest

from bootstrap import App, Repositories, build_app
from core.hil import Proposal, Suggestion
from core.target import TargetNotFoundError, type_name
from plugins.target.aircraft import Aircraft
from tests.core.collector.fakes import InMemoryCursorRepository, InMemoryDynamicDataRepository
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
            targets=InMemoryTargetRepository(),
            observables=InMemoryObservableTargetRepository(),
            cursors=InMemoryCursorRepository(),
            dynamic_data=InMemoryDynamicDataRepository(),
            parents=InMemoryParentEventRepository(),
            templates=InMemoryTemplateRepository(),
            events=InMemoryEventRepository(),
            runner_states=InMemoryRunnerStateRepository(),
            drafts=InMemoryDraftRepository(),
            suggestions=InMemorySuggestionRepository(),
        )
    )


def test_build_app_wires_everything() -> None:
    app = build()
    assert [type_name(t) for t in app.targets.types()] == ["aircraft"]
    assert [o.name for o in app.operator_registry.operators()] == ["count_hits", "close_report"]
    assert app.hil.allowed_actions() == ["add_target", "remove_target", "upsert_template"]
    assert app.parent_events.parents() == []


def test_accepted_suggestion_goes_through_public_method() -> None:
    app = build()
    app.targets.upsert_target(Aircraft(id="t1", name="MU5101", registration="B-2447"))
    app.parent_events.create("p1", "东海方向")

    def propose(**args: Any) -> Suggestion:
        s = Suggestion(
            source="alias_finder",
            reason="x",
            proposal=Proposal(action="add_target", target="p1", args=args),
        )
        app.hil.receive(s)
        return s

    # 目标不存在 → 公开方法的校验照常生效，建议保持待审
    bad = propose(target_id="ghost")
    with pytest.raises(TargetNotFoundError):
        app.hil.accept(bad.id)
    assert app.hil.pending() == [bad]

    good = propose(target_id="t1")
    app.hil.accept(good.id)
    assert app.parent_events.get("p1").target_ids() == {"t1"}
