"""README 里的模板定义示例必须能真实编译，避免文档过时。"""

import json
import pathlib
import re

from core.event import TemplateDef
from tests.core.event.conftest import Env

README = pathlib.Path(__file__).resolve().parents[1] / "README.md"


def test_readme_template_example_compiles() -> None:
    text = README.read_text(encoding="utf-8")
    match = re.search(
        r"<!-- template-example:start -->\s*```json\n(.*?)```\s*<!-- template-example:end -->",
        text,
        re.S,
    )
    assert match, "README 里找不到模板定义示例"
    template_def = TemplateDef.model_validate(json.loads(match.group(1)))

    env = Env()
    parent = env.parent_events.create("p1", "东海方向")
    parent.add_target("t1")
    parent.add_target("t2")
    template = parent.upsert_template(template_def)
    assert {o.observable_id for o in template.observable_defs} == {"t1:position", "t2:position"}
