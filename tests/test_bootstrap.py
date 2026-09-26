from typing import Any

import pytest

from bootstrap import App, Repositories, build_app
from core.contracts import Proposal, Suggestion
from core.target import NoUpstreamError, Target
from tests.core.collector.fakes import InMemoryCursorRepository, InMemoryDynamicDataRepository
from tests.core.event.fakes import (
    InMemoryInstanceRepository,
    InMemoryParentEventRepository,
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
            instances=InMemoryInstanceRepository(),
            drafts=InMemoryDraftRepository(),
            suggestions=InMemorySuggestionRepository(),
        )
    )


def test_build_app_wires_everything() -> None:
    app = build()
    assert [t.name for t in app.targets.types()] == ["aircraft"]
    assert [o.name for o in app.operators.operators()] == ["count_hits", "close_report"]
    assert app.hil.allowed_actions() == ["add_target", "remove_target", "upsert_template"]
    assert app.events.parents() == []


def test_accepted_suggestion_goes_through_public_method() -> None:
    app = build()
    app.targets.upsert_target(
        Target(id="t1", type="aircraft", name="MU5101", attributes={"registration": "B-2447"})
    )
    app.events.create("p1", "东海方向")

    def propose(**args: Any) -> Suggestion:
        s = Suggestion(
            source="alias_finder",
            reason="x",
            proposal=Proposal(action="add_target", target="p1", args=args),
        )
        app.hil.receive(s)
        return s

    # 没有上游能服务 → 公开方法的校验照常生效，建议保持待审
    bad = propose(target_id="t1", focus="position")
    with pytest.raises(NoUpstreamError):
        app.hil.accept(bad.id)
    assert app.hil.pending() == [bad]
