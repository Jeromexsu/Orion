from core.event import TemplateDef
from tests.core.event.conftest import Env, mount, template


def test_digest_rolls_one_machine_draft(env: Env) -> None:
    parent = env.parent_events.create("p1", "东海方向")
    parent.add_target("t1")
    parent.upsert_template(TemplateDef.model_validate(template(threshold=9)))

    first = parent.digest()
    assert first.title == "东海方向 汇总"
    assert "- MU5101" in first.content
    assert "- 进入区域 v1：已结束 0 个周期，未开启" in first.content

    parent.runner("enter-zone").on_observation(env.envelope(20, 20))
    parent.runner("enter-zone").on_observation(env.envelope(5, 5))
    second = parent.digest()
    assert (second.id, second.version) == (first.id, 2)
    assert "2026 周期进行中 {'hits': 1}" in second.content

    parent.upsert_template(TemplateDef.model_validate(template(version=2)))
    assert "进入区域 v1（v2 待下个周期生效）" in parent.digest().content

    # 分析师接手后，下一次汇总另起一份草稿
    env.reports.edit(first.id, "人工修改")
    assert parent.digest().id != first.id


def test_digest_all_isolates_failures(env: Env) -> None:
    env.parent_events.create("p1", "a")
    env.parent_events.create("p2", "b")
    assert env.parent_events.digest_all() == []
    assert len(env.drafts.items) == 2


def test_close_report_hook_writes_draft(env: Env) -> None:
    parent = env.parent_events.create("p1", "东海方向")
    parent.add_target("t1")
    parent.upsert_template(
        TemplateDef.model_validate(
            template(threshold=1, mounts=[mount("closeReport", "closed", title="进入告警")])
        )
    )
    parent.runner("enter-zone").on_observation(env.envelope(20, 20))
    parent.runner("enter-zone").on_observation(env.envelope(5, 5))

    (draft,) = env.reports.list_by_parent("p1")
    assert draft.title == "进入告警"
    assert "涉及目标：MU5101" in draft.content
    assert "'hits': 1" in draft.content
