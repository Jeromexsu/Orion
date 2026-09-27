from typing import Any

import pytest

from core.condition_engine import ConditionCompiler, EvaluatorRegistry
from core.event import EventTemplate, TemplateCompileError, TemplateCompiler, TemplateDef
from core.hooks import MountCompiler
from plugins.condition_engine.on_enter import OnEnter
from plugins.hooks.count_hits import CountHitsParams
from tests.core.event.conftest import Env, enter, mount, template
from tests.core.event.fakes import StaticUpstreamCatalog


def compile_(env: Env, raw: dict[str, Any]) -> EventTemplate:
    return env.services.template_compiler.compile(TemplateDef.model_validate(raw))


def test_compile(env: Env) -> None:
    t = compile_(env, template(threshold=3))
    assert t.target_ids == {"t1"}
    assert [o.observable_id for o in t.observable_defs] == ["t1:position"]
    (mount_,) = t.rules[0].mounts
    assert mount_.hook.name == "countHits"
    assert mount_.params == CountHitsParams(threshold=3)   # 编译好的是有类型的参数


def test_observables_are_compiled_once(env: Env) -> None:
    t = compile_(env, template(upstreams=["adsb", "radar"]))
    (compiled,) = t.compiled_observables
    # 编译结果引用的就是 TargetManager 里的单例，runner 直接用它订阅，不再解析
    assert compiled.observable is env.observables.get_observable("t1", "position")
    assert compiled.upstreams == {"adsb", "radar"}


def test_failed_compile_creates_no_observable(env: Env) -> None:
    with pytest.raises(TemplateCompileError):
        compile_(env, template(threshold=0))  # 可观测目标声明合法，但钩子参数非法
    assert env.observables.observables() == []


def test_open_condition_is_required(env: Env) -> None:
    raw = template()
    del raw["open_condition_def"]
    with pytest.raises(ValueError):
        compile_(env, raw)


def test_compile_collects_errors(env: Env) -> None:
    raw = template(
        mounts=[
            mount("countHits", "rule_hit"),     # 和默认那个重名；rule_hit 不能写在 at
            mount("nope", "post"),
            mount("recorder", rules=["ghost"]),
            mount("recorder", name="idle"),     # 哪儿都没挂
        ]
    )
    raw["observable_defs"].append(dict(raw["observable_defs"][0]))
    raw["open_condition_def"] = enter("t2:position")  # 未在可观测目标声明里
    raw["rule_defs"].append({"name": "enter", "condition_def": enter("ghost:position")})
    with pytest.raises(TemplateCompileError) as info:
        compile_(env, raw)
    errors = info.value.errors
    assert any("observable_def 't1:position': duplicate" in e for e in errors)
    # 条件只能引用已声明的观测：t2 未声明，对条件引擎来说就是未知目标
    assert any(e.startswith("open_condition_def: root: unknown observable 't2:position'") for e in errors)
    assert any("duplicate rule names ['enter']" in e for e in errors)
    assert any(e.startswith("rule 'enter': root: unknown observable") for e in errors)
    assert any("duplicate mount names ['countHits']" in e for e in errors)
    assert any("mount 'countHits': 'rule_hit' is not a place of its own" in e for e in errors)
    assert any(e.startswith("mount 'nope': unknown hook") for e in errors)
    assert any("mount 'recorder': unknown rules ['ghost']" in e for e in errors)
    assert any("mount 'idle': mounted nowhere" in e for e in errors)


def test_one_mount_runs_at_several_places(env: Env) -> None:
    t = compile_(env, template(mounts=[mount("closeReport", "closed", rules=["enter"])]))
    (report,) = t.mounts_at("closed")
    assert report.name == "closeReport"
    assert [m.name for m in t.rules[0].mounts] == ["countHits", "closeReport"]
    assert t.rules[0].mounts[1] is report       # 同一个挂载，同一份状态


def test_invalid_mount_params(env: Env) -> None:
    with pytest.raises(TemplateCompileError):
        compile_(env, template(threshold=0))


def test_observable_defs_are_resolved(env: Env) -> None:
    raw = template(upstreams=["adsb", "satellite"])
    raw["observable_defs"].append({"target_id": "ghost", "observed_point": "position", "upstreams": ["adsb"]})
    raw["observable_defs"].append({"target_id": "t2", "observed_point": "fuel", "upstreams": ["adsb"]})
    with pytest.raises(TemplateCompileError) as info:
        compile_(env, raw)
    errors = info.value.errors
    assert any("observable_def 't1:position': upstreams ['satellite'] not in available" in e for e in errors)
    assert any(e.startswith("observable_def 'ghost:position': ") for e in errors)
    assert any(e.startswith("observable_def 't2:fuel': ") for e in errors)
    assert any("observable_def 't2:fuel': aircraft has no observed point 'fuel'" in e for e in errors)


def test_observable_without_upstream_rejected(env: Env) -> None:
    evaluators = EvaluatorRegistry()
    evaluators.register(OnEnter())
    compiler = TemplateCompiler(
        ConditionCompiler(evaluators),
        MountCompiler(env.hook_registry),
        env.targets,
        StaticUpstreamCatalog({}),                  # 没有任何上游能观测
        env.observables,
    )
    with pytest.raises(TemplateCompileError) as info:
        compiler.compile(TemplateDef.model_validate(template()))
    assert any("no upstream can observe it" in e for e in info.value.errors)
    assert env.observables.observables() == []
