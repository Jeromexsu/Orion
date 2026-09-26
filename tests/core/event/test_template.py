import pytest

from core.event import SubEventTemplate, TemplateCompileError, TemplateDef, TemplateScopeError
from tests.core.event.conftest import Env, mount, template


def compile_(env: Env, raw: dict[str, object]) -> SubEventTemplate:
    return SubEventTemplate.compile(
        TemplateDef.model_validate(raw), env.runtime.conditions, env.operators
    )


def test_compile_normalizes_operator_params(env: Env) -> None:
    t = compile_(env, template(threshold=3))
    assert t.targets == {"t1:position"}
    assert t.rules[0].hooks[0].params == {"threshold": 3}


def test_compile_collects_errors(env: Env) -> None:
    raw = template(target="ghost:position", hooks=[mount("count_hits", "rule_hit"), mount("nope", "post")])
    raw["rules"].append(  # type: ignore[union-attr]
        {
            "name": "enter",
            "condition": {"kind": "leaf", "target": "t1:position", "type": "onEnter", "params": {"area": [(0, 0), (0, 1), (1, 1)]}},
            "hooks": [mount("recorder", "post")],
        }
    )
    with pytest.raises(TemplateCompileError) as info:
        compile_(env, raw)
    errors = info.value.errors
    assert any("duplicate rule names ['enter']" in e for e in errors)
    assert any(e.startswith("rule 'enter': root: unknown target") for e in errors)
    assert any("rule hooks must mount at 'rule_hit'" in e for e in errors)
    assert any("hook 0: 'rule_hit' hooks belong on a rule" in e for e in errors)
    assert any(e.startswith("hook 1: ") and "nope" in e for e in errors)


def test_invalid_operator_params(env: Env) -> None:
    with pytest.raises(TemplateCompileError):
        compile_(env, template(threshold=0))


def test_validate_scope(env: Env) -> None:
    t = compile_(env, template())
    t.validate({"t1:position", "t2:position"})
    with pytest.raises(TemplateScopeError):
        t.validate({"t2:position"})
