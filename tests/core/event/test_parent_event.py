from typing import Any

import pytest

from core.event import (
    DuplicateParentEventError,
    EventManager,
    ParentEvent,
    ParentEventNotFoundError,
    SubEventSlot,
    TargetStillReferencedError,
    TemplateDef,
    TemplateNotFoundError,
    TemplateScopeError,
    TemplateVersionError,
)
from core.target import TargetNotFoundError, UnsupportedUpstreamError
from tests.core.event.conftest import Env, mount, template

INSIDE, OUTSIDE = (5, 5), (20, 20)


def open_cycle(env: Env, slot: SubEventSlot) -> None:
    """先在区域外、再进入：开启条件命中，开实例（hits=1）。"""
    slot.on_data(env.data(*OUTSIDE))
    slot.on_data(env.data(*INSIDE))


def make_parent(env: Env, **kwargs: Any) -> ParentEvent:
    parent = env.events.create("p1", "东海方向")
    parent.add_target("t1")
    parent.upsert_template(TemplateDef.model_validate(template(**kwargs)))
    return parent


# ---------------------------------------------------------------- 父事件：静态命名空间


def test_create_and_get(env: Env) -> None:
    parent = env.events.create("p1", "x")
    assert env.events.get("p1") is parent
    assert env.parents.items["p1"].name == "x"
    with pytest.raises(DuplicateParentEventError):
        env.events.create("p1", "y")
    with pytest.raises(ParentEventNotFoundError):
        env.events.get("nope")


def test_namespace_holds_static_targets_only(env: Env) -> None:
    parent = env.events.create("p1", "x")
    parent.add_target("t1")
    assert parent.target_ids() == {"t1"}
    assert env.parents.items["p1"].targets == ["t1"]
    assert env.targets.active_observables() == []  # 父事件不订阅任何东西
    with pytest.raises(TargetNotFoundError):
        parent.add_target("ghost")


def test_template_must_observe_namespace_targets(env: Env) -> None:
    parent = env.events.create("p1", "x")
    with pytest.raises(TemplateScopeError):
        parent.upsert_template(TemplateDef.model_validate(template()))


def test_unavailable_upstream_rejected_at_upsert(env: Env) -> None:
    parent = env.events.create("p1", "x")
    parent.add_target("t1")
    with pytest.raises(UnsupportedUpstreamError):
        parent.upsert_template(TemplateDef.model_validate(template(upstreams=["satellite"])))
    with pytest.raises(TemplateNotFoundError):
        parent.slot("enter-zone")


def test_remove_target_observed_by_template(env: Env) -> None:
    parent = make_parent(env)
    with pytest.raises(TargetStillReferencedError):
        parent.remove_target("t1")
    parent.remove_template("enter-zone")
    parent.remove_target("t1")
    assert parent.target_ids() == frozenset()


# ---------------------------------------------------------------- slot：订阅与开启


def test_slot_subscribes_per_observation(env: Env) -> None:
    parent = make_parent(env, upstreams=["radar"])
    slot = parent.slot("enter-zone")
    (obs,) = env.targets.active_observables()
    assert obs.referencers() == {slot}
    assert obs.subscription(slot) == {"radar"}
    assert slot.target_names() == {"t1:position": "MU5101"}


def test_open_condition_gates_instances(env: Env) -> None:
    parent = make_parent(env)
    slot = parent.slot("enter-zone")

    slot.on_data(env.data(*OUTSIDE))
    assert slot.active is None
    assert slot.open_state == {"root": {"inside": False}}

    slot.on_data(env.data(*INSIDE))  # 进入 → 开实例，这条数据交给实例
    instance = slot.active
    assert instance is not None
    assert instance.cycle == 2026
    assert instance.status == {"hits": 1}
    assert env.slot_states.get("p1", "enter-zone") == {"root": {"inside": True}}


def test_lifecycle_and_open_state_during_run(env: Env) -> None:
    parent = make_parent(env, threshold=3, hooks=[mount("recorder", m) for m in ("created", "closed")])
    slot = parent.slot("enter-zone")
    slot.on_data(env.data(*OUTSIDE))
    slot.on_data(env.data(*INSIDE))  # 开启，hits=1
    first = slot.active
    assert first is not None

    slot.on_data(env.data(*OUTSIDE))  # 运行期间开启条件照常评估、状态保持最新
    assert slot.open_state == {"root": {"inside": False}}
    slot.on_data(env.data(*INSIDE))  # hits=2（开启条件命中，但已有实例，不开新的）
    assert slot.active is first
    slot.on_data(env.data(*OUTSIDE))
    slot.on_data(env.data(*INSIDE))  # hits=3 → 收敛关闭
    assert first.is_closed and slot.active is None
    assert env.log.calls == [("recorder", "created"), ("recorder", "closed")]

    record = env.instances.items[first.id]
    assert (record.close_reason, record.cycle) == ("converged", 2026)

    slot.on_data(env.data(*INSIDE))  # 仍在区域内：不算再次进入，不开新实例
    assert slot.active is None
    slot.on_data(env.data(*OUTSIDE))
    slot.on_data(env.data(*INSIDE))  # 离开后再进入 → 下一个周期
    assert slot.active is not None and slot.active is not first
    assert len(slot.history()) == 2


def test_unsubscribed_data_ignored(env: Env) -> None:
    parent = make_parent(env)
    slot = parent.slot("enter-zone")
    slot.on_data(env.data(*INSIDE, observable_id="t2:position"))
    assert slot.active is None and slot.open_state == {}


def test_status_hook_recursion_is_bounded(env: Env) -> None:
    parent = make_parent(env, threshold=5, hooks=[mount("echo", "status_updated")])
    slot = parent.slot("enter-zone")
    open_cycle(env, slot)
    slot.on_data(env.data(*OUTSIDE))
    slot.on_data(env.data(*INSIDE))
    active = slot.active
    assert active is not None
    assert active.status == {"hits": 2, "echoed": 2}


def test_suggestions_flow_to_sink(env: Env) -> None:
    parent = make_parent(env, hooks=[mount("spotter", "pre")])
    slot = parent.slot("enter-zone")
    slot.on_data(env.data(*OUTSIDE))  # 未开启：实例级钩子不跑
    assert env.sink.received == []
    slot.on_data(env.data(*INSIDE))
    assert [s.reason for s in env.sink.received] == ["saw MU5101"]


def test_operator_failure_is_isolated(env: Env) -> None:
    parent = make_parent(env, hooks=[mount("boom", "pre"), mount("recorder", "pre")])
    open_cycle(env, parent.slot("enter-zone"))
    assert env.log.calls == [("recorder", "pre")]


def test_manual_close(env: Env) -> None:
    parent = make_parent(env, threshold=9)
    slot = parent.slot("enter-zone")
    open_cycle(env, slot)
    instance = slot.active
    assert instance is not None
    slot.close_active("analyst_closed")
    assert slot.active is None
    assert env.instances.items[instance.id].close_reason == "analyst_closed"


# ---------------------------------------------------------------- 换版本：下个周期生效


def test_new_version_waits_for_current_cycle(env: Env) -> None:
    parent = make_parent(env, threshold=3)
    slot = parent.slot("enter-zone")
    open_cycle(env, slot)
    running = slot.active
    assert running is not None

    parent.upsert_template(TemplateDef.model_validate(template(version=2, upstreams=["radar"])))
    assert slot.template.version == 1
    assert slot.pending is not None and slot.pending.version == 2
    assert env.parents.items["p1"].templates[0].pending_version == 2
    assert not running.is_closed
    with pytest.raises(TemplateVersionError):
        parent.upsert_template(TemplateDef.model_validate(template(version=2)))

    slot.close_active("season_over")  # 周期结束 → 切换到 v2、重新订阅、开启条件状态清空
    assert (slot.template.version, slot.pending) == (2, None)
    assert slot.open_state == {}
    (obs,) = env.targets.active_observables()
    assert obs.subscription(slot) == {"radar"}
    ref = env.parents.items["p1"].templates[0]
    assert (ref.version, ref.pending_version) == (2, None)


def test_new_version_applies_immediately_when_idle(env: Env) -> None:
    parent = make_parent(env)
    parent.upsert_template(TemplateDef.model_validate(template(version=2)))
    assert parent.slot("enter-zone").template.version == 2
    assert env.templates.list_versions("enter-zone") == [1, 2]


def test_remove_template_disposes_slot(env: Env) -> None:
    parent = make_parent(env)
    slot = parent.slot("enter-zone")
    open_cycle(env, slot)
    instance = slot.active
    assert instance is not None

    parent.remove_template("enter-zone")
    assert env.instances.items[instance.id].close_reason == "template_removed"
    assert env.targets.active_observables() == []
    assert env.slot_states.get("p1", "enter-zone") is None
    with pytest.raises(TemplateNotFoundError):
        parent.remove_template("enter-zone")


# ---------------------------------------------------------------- 重启恢复


def test_restore(env: Env) -> None:
    parent = make_parent(env, threshold=9)
    slot = parent.slot("enter-zone")
    open_cycle(env, slot)
    active = slot.active
    assert active is not None
    parent.upsert_template(TemplateDef.model_validate(template(version=2)))  # 挂起

    # 模拟重启：新的 TargetManager（订阅关系为空）+ 同一批仓库
    targets = env.make_targets()
    events = EventManager(env.make_runtime(targets))
    assert events.restore() == []

    restored = events.get("p1").slot("enter-zone")
    (obs,) = targets.active_observables()
    assert obs.subscription(restored) == {"adsb"}
    assert restored.template.version == 1
    assert restored.pending is not None and restored.pending.version == 2
    assert restored.active is not None and restored.active.id == active.id
    assert restored.active.status == {"hits": 1}
    assert restored.open_state == {"root": {"inside": True}}

    # 规则的条件状态也恢复了：仍在区域内不算再次进入，hits 不变
    # （若状态丢失，首次观测按 initial_as_enter=True 会误判为进入，hits 变成 2）
    restored.on_data(env.data(6, 6))
    assert restored.active.status == {"hits": 1}


def test_restore_failure_is_isolated(env: Env) -> None:
    make_parent(env)
    env.templates.items.clear()
    events = EventManager(env.runtime)
    assert events.restore() == ["p1"]
