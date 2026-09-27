from typing import Any

import pytest

from core.event import EventTemplate, TemplateCompileError, TemplateDef
from tests.core.event.conftest import Env, enter, mount, template


def compile_(env: Env, raw: dict[str, Any]) -> EventTemplate:
    return env.services.template_compiler.compile(TemplateDef.model_validate(raw))


def test_compile(env: Env) -> None:
    t = compile_(env, template(threshold=3))
    assert t.target_ids == {"t1"}
    assert [o.observable_id for o in t.observable_defs] == ["t1:position"]
    assert t.rules[0].hook_defs[0].params == {"threshold": 3}


def test_observables_are_compiled_once(env: Env) -> None:
    t = compile_(env, template(upstreams=["adsb", "radar"]))
    (compiled,) = t.compiled_observables
    # 编译结果引用的就是 TargetManager 里的单例，runner 直接用它订阅，不再解析
    assert compiled.observable is env.targets.get_observable("t1", "position")
    assert compiled.upstreams == {"adsb", "radar"}


def test_failed_compile_creates_no_observable(env: Env) -> None:
    with pytest.raises(TemplateCompileError):
        compile_(env, template(threshold=0))  # 可观测目标声明合法，但算子参数非法
    assert env.observable_repo.items == {}


def test_open_condition_is_required(env: Env) -> None:
    raw = template()
    del raw["open_condition_def"]
    with pytest.raises(ValueError):
        compile_(env, raw)


def test_compile_collects_errors(env: Env) -> None:
    raw = template(hooks=[mount("count_hits", "rule_hit"), mount("nope", "post")])
    raw["observable_defs"].append(dict(raw["observable_defs"][0]))
    raw["open_condition_def"] = enter("t2:position")  # 未在可观测目标声明里
    raw["rule_defs"].append(
        {
            "name": "enter",
            "condition_def": enter("ghost:position"),
            "hook_defs": [mount("recorder", "post")],
        }
    )
    with pytest.raises(TemplateCompileError) as info:
        compile_(env, raw)
    errors = info.value.errors
    assert any("observable_def 't1:position': duplicate" in e for e in errors)
    # 条件只能引用已声明的观测：t2 未声明，对条件引擎来说就是未知目标
    assert any(e.startswith("open_condition_def: root: unknown observable 't2:position'") for e in errors)
    assert any("duplicate rule names ['enter']" in e for e in errors)
    assert any(e.startswith("rule 'enter': root: unknown observable") for e in errors)
    assert any("rule hooks must mount at 'rule_hit'" in e for e in errors)
    assert any("hook 0: 'rule_hit' hooks belong on a rule" in e for e in errors)
    assert any(e.startswith("hook 1: ") and "nope" in e for e in errors)


def test_invalid_operator_params(env: Env) -> None:
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
