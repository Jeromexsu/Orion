from bootstrap import Repositories, build_app
from tests.core.collector.fakes import InMemoryCursorRepository, InMemoryDynamicDataRepository
from tests.core.event.fakes import (
    InMemoryInstanceRepository,
    InMemoryParentEventRepository,
    InMemoryTemplateRepository,
    RecordingSink,
)
from tests.core.target.fakes import InMemoryObservableTargetRepository, InMemoryTargetRepository


def test_build_app_wires_everything() -> None:
    app = build_app(
        Repositories(
            targets=InMemoryTargetRepository(),
            observables=InMemoryObservableTargetRepository(),
            cursors=InMemoryCursorRepository(),
            dynamic_data=InMemoryDynamicDataRepository(),
            parents=InMemoryParentEventRepository(),
            templates=InMemoryTemplateRepository(),
            instances=InMemoryInstanceRepository(),
        ),
        suggestions=RecordingSink(),
    )
    assert [t.name for t in app.targets.types()] == ["aircraft"]
    assert [o.name for o in app.operators.operators()] == ["count_hits"]
    assert app.events.parents() == []
