from typing import Any

import pytest

from core.event import (
    DuplicateParentEventError,
    EventRunner,
    ParentEvent,
    ParentEventManager,
    ParentEventNotFoundError,
    TargetStillReferencedError,
    TemplateCompileError,
    TemplateDef,
    TemplateNotFoundError,
    TemplateScopeError,
    TemplateVersionError,
)
from core.target import TargetNotFoundError
from tests.core.event.conftest import Env, mount, template

INSIDE, OUTSIDE = (5, 5), (20, 20)


def open_cycle(env: Env, runner: EventRunner) -> None:
    """先在区域外、再进入：开启条件命中，开实例（hits=1）。"""
    runner.on_observation(env.envelope(*OUTSIDE))
    runner.on_observation(env.envelope(*INSIDE))


def make_parent(env: Env, **kwargs: Any) -> ParentEvent:
    parent = env.parent_events.create("p1", "东海方向")
    parent.add_target("t1")
    parent.upsert_template(TemplateDef.model_validate(template(**kwargs)))
    return parent


# ---------------------------------------------------------------- 父事件：静态命名空间


def test_create_and_get(env: Env) -> None:
    parent = env.parent_events.create("p1", "x")
    assert env.parent_events.get("p1") is parent
    assert env.parents.items["p1"].name == "x"
    with pytest.raises(DuplicateParentEventError):
        env.parent_events.create("p1", "y")
    with pytest.raises(ParentEventNotFoundError):
        env.parent_events.get("nope")


def test_namespace_holds_static_targets_only(env: Env) -> None:
    parent = env.parent_events.create("p1", "x")
    parent.add_target("t1")
    assert parent.target_ids() == {"t1"}
    assert env.parents.items["p1"].targets == ["t1"]
    assert env.targets.active_observables() == []  # 父事件不订阅任何东西
    with pytest.raises(TargetNotFoundError):
        parent.add_target("ghost")


def test_template_must_observe_namespace_targets(env: Env) -> None:
    parent = env.parent_events.create("p1", "x")
    with pytest.raises(TemplateScopeError):
        parent.upsert_template(TemplateDef.model_validate(template()))
    # 在编译之前就被拒：没有为越界的模板创建可观测目标，也没有存定义
    assert env.targets.find_observable("t1:position") is None
    assert env.templates.list_versions("enter-zone") == []


def test_version_checked_before_compile(env: Env) -> None:
    parent = make_parent(env)
    bad = template(version=1, threshold=0)  # 版本号不增，且参数非法
    with pytest.raises(TemplateVersionError):  # 先报版本，不白做编译
        parent.upsert_template(TemplateDef.model_validate(bad))


def test_unavailable_upstream_rejected_at_upsert(env: Env) -> None:
    parent = env.parent_events.create("p1", "x")
    parent.add_target("t1")
    with pytest.raises(TemplateCompileError):
        parent.upsert_template(TemplateDef.model_validate(template(upstreams=["satellite"])))
    with pytest.raises(TemplateNotFoundError):
        parent.runner("enter-zone")


def test_remove_target_observed_by_template(env: Env) -> None:
    parent = make_parent(env)
    with pytest.raises(TargetStillReferencedError):
        parent.remove_target("t1")
    parent.remove_template("enter-zone")
    parent.remove_target("t1")
    assert parent.target_ids() == frozenset()


# ---------------------------------------------------------------- runner：订阅与开启


def test_slot_subscribes_per_observation(env: Env) -> None:
    parent = make_parent(env, upstreams=["radar"])
    runner = parent.runner("enter-zone")
    (obs,) = env.targets.active_observables()
    assert obs.subscribers() == {runner}
    assert obs.subscription(runner) == {"radar"}
    assert runner.target_names() == {"t1:position": "MU5101"}


def test_open_condition_gates_instances(env: Env) -> None:
    parent = make_parent(env)
    runner = parent.runner("enter-zone")

    runner.on_observation(env.envelope(*OUTSIDE))
    assert runner.active is None
    assert runner.open_state == {"root": {"inside": False}}

    runner.on_observation(env.envelope(*INSIDE))  # 进入 → 开实例，这条数据交给实例
    instance = runner.active
    assert instance is not None
    assert instance.cycle == 2026
    assert instance.status == {"hits": 1}
    assert env.runner_states.get("p1", "enter-zone") == {"root": {"inside": True}}


def test_lifecycle_and_open_state_during_run(env: Env) -> None:
    parent = make_parent(env, threshold=3, hooks=[mount("recorder", m) for m in ("created", "closed")])
    runner = parent.runner("enter-zone")
    runner.on_observation(env.envelope(*OUTSIDE))
    runner.on_observation(env.envelope(*INSIDE))  # 开启，hits=1
    first = runner.active
    assert first is not None

    runner.on_observation(env.envelope(*OUTSIDE))  # 运行期间开启条件照常评估、状态保持最新
    assert runner.open_state == {"root": {"inside": False}}
    runner.on_observation(env.envelope(*INSIDE))  # hits=2（开启条件命中，但已有实例，不开新的）
    assert runner.active is first
    runner.on_observation(env.envelope(*OUTSIDE))
    runner.on_observation(env.envelope(*INSIDE))  # hits=3 → 收敛关闭
    assert first.is_closed and runner.active is None
    assert env.log.calls == [("recorder", "created"), ("recorder", "closed")]

    record = env.events.items[first.id]
    assert (record.close_reason, record.cycle) == ("converged", 2026)

    runner.on_observation(env.envelope(*INSIDE))  # 仍在区域内：不算再次进入，不开新实例
    assert runner.active is None
    runner.on_observation(env.envelope(*OUTSIDE))
    runner.on_observation(env.envelope(*INSIDE))  # 离开后再进入 → 下一个周期
    assert runner.active is not None and runner.active is not first
    assert len(runner.history()) == 2


def test_unsubscribed_data_ignored(env: Env) -> None:
    parent = make_parent(env)
    runner = parent.runner("enter-zone")
    runner.on_observation(env.envelope(*INSIDE, observable_id="t2:position"))
    assert runner.active is None and runner.open_state == {}


def test_status_hook_recursion_is_bounded(env: Env) -> None:
    parent = make_parent(env, threshold=5, hooks=[mount("echo", "status_updated")])
    runner = parent.runner("enter-zone")
    open_cycle(env, runner)
    runner.on_observation(env.envelope(*OUTSIDE))
    runner.on_observation(env.envelope(*INSIDE))
    active = runner.active
    assert active is not None
    assert active.status == {"hits": 2, "echoed": 2}


def test_suggestions_flow_to_sink(env: Env) -> None:
    parent = make_parent(env, hooks=[mount("spotter", "pre")])
    runner = parent.runner("enter-zone")
    runner.on_observation(env.envelope(*OUTSIDE))  # 未开启：实例级钩子不跑
    assert env.sink.received == []
    runner.on_observation(env.envelope(*INSIDE))
    assert [s.reason for s in env.sink.received] == ["saw MU5101"]


def test_operator_failure_is_isolated(env: Env) -> None:
    parent = make_parent(env, hooks=[mount("boom", "pre"), mount("recorder", "pre")])
    open_cycle(env, parent.runner("enter-zone"))
    assert env.log.calls == [("recorder", "pre")]


def test_manual_close(env: Env) -> None:
    parent = make_parent(env, threshold=9)
    runner = parent.runner("enter-zone")
    open_cycle(env, runner)
    instance = runner.active
    assert instance is not None
    runner.close_active("analyst_closed")
    assert runner.active is None
    assert env.events.items[instance.id].close_reason == "analyst_closed"


# ---------------------------------------------------------------- 换版本：下个周期生效


def test_new_version_waits_for_current_cycle(env: Env) -> None:
    parent = make_parent(env, threshold=3)
    runner = parent.runner("enter-zone")
    open_cycle(env, runner)
    running = runner.active
    assert running is not None

    parent.upsert_template(TemplateDef.model_validate(template(version=2, upstreams=["radar"])))
    assert runner.template.version == 1
    assert runner.pending is not None and runner.pending.version == 2
    assert env.parents.items["p1"].templates[0].pending_version == 2
    assert not running.is_closed
    with pytest.raises(TemplateVersionError):
        parent.upsert_template(TemplateDef.model_validate(template(version=2)))

    runner.close_active("season_over")  # 周期结束 → 切换到 v2、重新订阅、开启条件状态清空
    assert (runner.template.version, runner.pending) == (2, None)
    assert runner.open_state == {}
    (obs,) = env.targets.active_observables()
    assert obs.subscription(runner) == {"radar"}
    ref = env.parents.items["p1"].templates[0]
    assert (ref.version, ref.pending_version) == (2, None)


def test_new_version_applies_immediately_when_idle(env: Env) -> None:
    parent = make_parent(env)
    parent.upsert_template(TemplateDef.model_validate(template(version=2)))
    assert parent.runner("enter-zone").template.version == 2
    assert env.templates.list_versions("enter-zone") == [1, 2]


def test_remove_template_disposes_slot(env: Env) -> None:
    parent = make_parent(env)
    runner = parent.runner("enter-zone")
    open_cycle(env, runner)
    instance = runner.active
    assert instance is not None

    parent.remove_template("enter-zone")
    assert env.events.items[instance.id].close_reason == "template_removed"
    assert env.targets.active_observables() == []
    assert env.runner_states.get("p1", "enter-zone") is None
    with pytest.raises(TemplateNotFoundError):
        parent.remove_template("enter-zone")


# ---------------------------------------------------------------- 重启恢复


def test_restore(env: Env) -> None:
    parent = make_parent(env, threshold=9)
    runner = parent.runner("enter-zone")
    open_cycle(env, runner)
    active = runner.active
    assert active is not None
    parent.upsert_template(TemplateDef.model_validate(template(version=2)))  # 挂起

    # 模拟重启：新的 TargetManager（订阅关系为空）+ 同一批仓库
    targets = env.make_targets()
    events = env.make_parent_events(targets)
    assert events.restore() == []

    restored = events.get("p1").runner("enter-zone")
    (obs,) = targets.active_observables()
    assert obs.subscription(restored) == {"adsb"}
    assert restored.template.version == 1
    assert restored.pending is not None and restored.pending.version == 2
    assert restored.active is not None and restored.active.id == active.id
    assert restored.active.status == {"hits": 1}
    assert restored.open_state == {"root": {"inside": True}}

    # 规则的条件状态也恢复了：仍在区域内不算再次进入，hits 不变
    # （若状态丢失，首次观测按 initial_as_enter=True 会误判为进入，hits 变成 2）
    restored.on_observation(env.envelope(6, 6))
    assert restored.active.status == {"hits": 1}


def test_restore_failure_is_isolated(env: Env) -> None:
    make_parent(env)
    env.templates.items.clear()
    events = ParentEventManager(env.parents, env.services, env.runtime)
    assert events.restore() == ["p1"]
