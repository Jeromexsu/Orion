from typing import Any

import pytest

from core.event import SubEventTemplate, TemplateCompileError, TemplateDef, TemplateScopeError
from tests.core.event.conftest import Env, enter, mount, template


def compile_(env: Env, raw: dict[str, Any]) -> SubEventTemplate:
    return SubEventTemplate.compile(
        TemplateDef.model_validate(raw), env.runtime.conditions, env.operators
    )


def test_compile(env: Env) -> None:
    t = compile_(env, template(threshold=3))
    assert t.target_ids == {"t1"}
    assert [o.observable_id for o in t.observations] == ["t1:position"]
    assert t.open_tree.targets() == {"t1:position"}
    assert t.rules[0].hooks[0].params == {"threshold": 3}


def test_open_condition_is_required(env: Env) -> None:
    raw = template()
    del raw["open_condition"]
    with pytest.raises(ValueError):
        compile_(env, raw)


def test_compile_collects_errors(env: Env) -> None:
    raw = template(hooks=[mount("count_hits", "rule_hit"), mount("nope", "post")])
    raw["observations"].append(dict(raw["observations"][0]))
    raw["open_condition"] = enter("t2:position")  # 未在观测声明里
    raw["rules"].append(
        {"name": "enter", "condition": enter("ghost:position"), "hooks": [mount("recorder", "post")]}
    )
    with pytest.raises(TemplateCompileError) as info:
        compile_(env, raw)
    errors = info.value.errors
    assert any("duplicate observations ['t1:position']" in e for e in errors)
    assert any("open_condition: targets ['t2:position'] not in observations" in e for e in errors)
    assert any("duplicate rule names ['enter']" in e for e in errors)
    assert any(e.startswith("rule 'enter': root: unknown target") for e in errors)
    assert any("rule hooks must mount at 'rule_hit'" in e for e in errors)
    assert any("hook 0: 'rule_hit' hooks belong on a rule" in e for e in errors)
    assert any(e.startswith("hook 1: ") and "nope" in e for e in errors)


def test_invalid_operator_params(env: Env) -> None:
    with pytest.raises(TemplateCompileError):
        compile_(env, template(threshold=0))


def test_validate_namespace(env: Env) -> None:
    t = compile_(env, template())
    t.validate({"t1", "t2"})
    with pytest.raises(TemplateScopeError):
        t.validate({"t2"})
