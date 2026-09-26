from core.event import TemplateDef
from tests.core.event.conftest import Env, mount, template


def test_digest_rolls_one_machine_draft(env: Env) -> None:
    parent = env.events.create("p1", "东海方向")
    parent.add_target("t1", "position", ["adsb"])
    parent.upsert_template(TemplateDef.model_validate(template()))
    parent.on_data(env.data(20, 20))

    first = parent.digest()
    assert first.title == "东海方向 汇总"
    assert "- MU5101（position）" in first.content
    assert "- 进入区域：已收敛 0 次，进行中 {}" in first.content

    parent.on_data(env.data(5, 5))
    second = parent.digest()
    assert (second.id, second.version) == (first.id, 2)
    assert "进行中 {'hits': 1}" in second.content

    # 分析师接手后，下一次汇总另起一份草稿
    env.reports.edit(first.id, "人工修改")
    third = parent.digest()
    assert third.id != first.id


def test_digest_all_isolates_failures(env: Env) -> None:
    env.events.create("p1", "a")
    env.events.create("p2", "b")
    assert env.events.digest_all() == []
    assert len(env.drafts.items) == 2


def test_close_report_operator_writes_draft(env: Env) -> None:
    parent = env.events.create("p1", "东海方向")
    parent.add_target("t1", "position", ["adsb"])
    parent.upsert_template(
        TemplateDef.model_validate(
            template(threshold=1, hooks=[mount("close_report", "closed", title="进入告警")])
        )
    )
    parent.on_data(env.data(20, 20))
    parent.on_data(env.data(5, 5))

    (draft,) = env.reports.list_by_parent("p1")
    assert draft.title == "进入告警"
    assert "涉及目标：MU5101" in draft.content
    assert "'closed': True" in draft.content
