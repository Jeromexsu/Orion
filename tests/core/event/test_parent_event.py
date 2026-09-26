from typing import Any

import pytest

from core.event import (
    DuplicateParentEventError,
    EventManager,
    InstanceClosedError,
    ParentEvent,
    ParentEventNotFoundError,
    TargetStillReferencedError,
    TemplateDef,
    TemplateNotFoundError,
    TemplateScopeError,
    TemplateVersionError,
)
from core.target import UnsupportedUpstreamError
from tests.core.event.conftest import Env, mount, template


def make_parent(
    env: Env, hooks: list[dict[str, Any]] | None = None, threshold: int = 2
) -> ParentEvent:
    parent = env.events.create("p1", "东海方向")
    parent.add_target("t1", "position", ["adsb"])
    parent.upsert_template(TemplateDef.model_validate(template(threshold=threshold, hooks=hooks)))
    return parent


# ---------------------------------------------------------------- 目标池 / 模板


def test_create_and_get(env: Env) -> None:
    parent = env.events.create("p1", "x")
    assert env.events.get("p1") is parent
    assert env.parents.items["p1"].name == "x"
    with pytest.raises(DuplicateParentEventError):
        env.events.create("p1", "y")
    with pytest.raises(ParentEventNotFoundError):
        env.events.get("nope")


def test_add_target_acquires_and_persists(env: Env) -> None:
    parent = env.events.create("p1", "x")
    obs = parent.add_target("t1", "position", ["adsb"])
    assert parent in obs.referencers()
    assert env.targets.active_observables() == [obs]
    assert [r.target_id for r in env.parents.items["p1"].targets] == ["t1"]
    assert parent.target_names() == {"t1:position": "MU5101"}


def test_template_must_stay_in_pool(env: Env) -> None:
    parent = env.events.create("p1", "x")
    with pytest.raises(TemplateScopeError):
        parent.upsert_template(TemplateDef.model_validate(template()))


def test_remove_target_referenced_by_template(env: Env) -> None:
    parent = make_parent(env)
    with pytest.raises(TargetStillReferencedError):
        parent.remove_target("t1:position")
    parent.remove_template("enter-zone")
    parent.remove_target("t1:position")
    assert env.targets.active_observables() == []


def test_template_versions_must_increase(env: Env) -> None:
    parent = make_parent(env)
    with pytest.raises(TemplateVersionError):
        parent.upsert_template(TemplateDef.model_validate(template(version=1)))
    with pytest.raises(TemplateNotFoundError):
        parent.remove_template("nope")


# ---------------------------------------------------------------- 管道


def test_pipeline_opens_processes_and_closes(env: Env) -> None:
    parent = make_parent(env, hooks=[mount("recorder", m) for m in ("created", "pre", "post", "status_updated", "closed")])
    slot = parent.slot("enter-zone")

    parent.on_data(env.data(20, 20))  # 区域外：未命中
    first = slot.active
    assert first is not None
    assert first.status == {}

    parent.on_data(env.data(5, 5))  # 进入：命中 1 次
    assert first.status == {"hits": 1}

    parent.on_data(env.data(20, 20))  # 出去
    parent.on_data(env.data(5, 5))  # 再进入：命中 2 次 → 收敛关闭
    assert first.is_closed
    assert slot.active is None

    mounts = [m for _, m in env.log.calls]
    assert mounts[0] == "created"
    assert mounts.count("pre") == 4 and mounts.count("post") == 4
    assert mounts.count("status_updated") == 2
    assert mounts[-1] == "closed"

    record = env.instances.items[first.id]
    assert record.close_reason == "converged"
    assert record.status == {"hits": 2, "closed": True}
    assert record.condition_state == {"enter": {"root": {"inside": True}}}

    # 下一条相关数据开新实例
    parent.on_data(env.data(20, 20))
    assert slot.active is not None and slot.active is not first
    assert len(slot.history()) == 2


def test_irrelevant_data_does_not_open_instance(env: Env) -> None:
    parent = make_parent(env)
    parent.add_target("t2", "position", ["adsb"])
    parent.on_data(env.data(5, 5, observable_id="t2:position"))
    parent.on_data(env.data(5, 5, observable_id="t9:position"))
    assert parent.slot("enter-zone").active is None


def test_status_hook_recursion_is_bounded(env: Env) -> None:
    parent = make_parent(env, hooks=[mount("echo", "status_updated")])
    parent.on_data(env.data(20, 20))
    parent.on_data(env.data(5, 5))
    active = parent.slot("enter-zone").active
    assert active is not None
    assert active.status == {"hits": 1, "echoed": 1}


def test_suggestions_flow_to_sink(env: Env) -> None:
    parent = make_parent(env, hooks=[mount("spotter", "pre")])
    parent.on_data(env.data(20, 20))
    assert [s.reason for s in env.sink.received] == ["saw MU5101"]
    assert env.sink.received[0].evidence == ["adsb#0"]


def test_operator_failure_is_isolated(env: Env) -> None:
    parent = make_parent(env, hooks=[mount("boom", "pre"), mount("recorder", "pre")])
    parent.on_data(env.data(20, 20))
    assert env.log.calls == [("recorder", "pre")]


def test_replace_template_closes_current_instance(env: Env) -> None:
    parent = make_parent(env)
    parent.on_data(env.data(20, 20))
    old = parent.slot("enter-zone").active
    assert old is not None

    parent.upsert_template(TemplateDef.model_validate(template(version=2, threshold=5)))
    assert old.is_closed
    assert env.instances.items[old.id].close_reason == "template_replaced"
    assert parent.slot("enter-zone").template.version == 2
    assert env.templates.list_versions("enter-zone") == [1, 2]

    with pytest.raises(InstanceClosedError):
        old.process(env.data(5, 5))


# ---------------------------------------------------------------- 重启恢复


def test_restore_reacquires_targets_and_active_instances(env: Env) -> None:
    parent = make_parent(env, threshold=3)
    parent.on_data(env.data(20, 20))
    parent.on_data(env.data(5, 5))
    active = parent.slot("enter-zone").active
    assert active is not None

    # 模拟重启：新的 TargetManager（订阅者集合为空）+ 同一批仓库
    targets = env.make_targets()
    events = EventManager(env.make_runtime(targets))
    assert targets.active_observables() == []

    assert events.restore() == []
    restored = events.get("p1")
    assert [o.id for o in targets.active_observables()] == ["t1:position"]
    slot = restored.slot("enter-zone")
    assert slot.active is not None and slot.active.id == active.id
    assert slot.active.status == {"hits": 1}

    # 条件状态也恢复了：还在区域内，不算再次进入
    restored.on_data(env.data(6, 6))
    assert slot.active.status == {"hits": 1}


def test_restore_failure_is_isolated(env: Env) -> None:
    make_parent(env)
    env.templates.items.clear()
    events = EventManager(env.runtime)
    assert events.restore() == ["p1"]


def test_add_target_subscribes_chosen_upstreams(env: Env) -> None:
    parent = env.events.create("p1", "x")
    obs = parent.add_target("t1", "position", ["adsb"])
    assert obs.subscription(parent) == {"adsb"}
    assert env.parents.items["p1"].targets[0].upstreams == ["adsb"]

    with pytest.raises(UnsupportedUpstreamError):
        parent.add_target("t1", "position", ["radar"])
    assert obs.subscription(parent) == {"adsb"}  # 失败不改变原订阅


def test_restore_keeps_upstream_subscription(env: Env) -> None:
    parent = env.events.create("p1", "x")
    parent.add_target("t1", "position", ["adsb"])

    targets = env.make_targets()
    events = EventManager(env.make_runtime(targets))
    assert events.restore() == []
    (obs,) = targets.active_observables()
    assert obs.subscription(events.get("p1")) == {"adsb"}
