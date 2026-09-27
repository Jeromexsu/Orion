# 开发约定

## 提交前

```bash
uv run pytest && uv run pyright && uv run lint-imports
```

## Docstring

用 Google 风格（英文）。新写或改动的 docstring 按此写；现有的中文 docstring 逐步迁移。

- 首行一句话说明做什么。
- 正文写读者最需要的：副作用（写库、推进游标、创建对象、订阅）、跳过 / 过滤的规则、**不做什么**（容易误以为它做的事）。
- `Args:` / `Returns:` / `Raises:` 只写类型标注说不出来的信息，不复述参数名和类型。
- 术语必须精确，按 [docs/glossary.md](docs/glossary.md)：
  observable target（可观测目标）≠ target（静态目标）；observation（观测）≠ envelope（观测外壳）；
  upstream（上游，名字）≠ upstream adapter（接入上游的插件）。

```python
def _collect_upstream(self, observable: ObservableTarget, upstream: str) -> list[ObservationEnvelope]:
    """Collect new observations of one observable target from one upstream.

    Stores them and advances the cursor of this (observable target, upstream) pair.
    Does not publish: collect_one publishes once all upstreams are done.

    Args:
        observable: The observable target to collect for.
        upstream: Name of the upstream adapter to query.

    Returns:
        Newly stored envelopes, sorted by occurred_at.
    """
```

## 命名

- 纯数据定义的类型以 `Def` 结尾，装着它的字段以 `_def` / `_defs` 结尾；运行时对象不带后缀。
- 注入的依赖按具体类型命名：`TargetManager` → `target_manager`，`TemplateRepository` → `template_repository`。
- 行为类用普通类，跨 JSON 边界的纯数据用 Pydantic，不用 dataclass。

## 插件

目标类型、观察点、查询键、判断方式、上游适配器、算子都用装饰器声明（`@target_type` / `@observed_point` / `@query_key` /
`@evaluator` / `@upstream_adapter` / `@operator`，字段用 `provides(...)`）。判断方式同时继承 `Evaluator[判定标准模型]`，
`op` 默认类名首字母小写；上游适配器继承 `UpstreamAdapter`，上游名默认类名去掉 Adapter 后缀、首字母小写。
算子继承 `Operator[参数模型]` 并用 `@operator(mount_points=..., scopes=..., proposes=...)` 声明，`name` 默认类名首字母小写；
直接作用只能是 `external` / `event`，父事件和目标只能提建议（`proposes=True`）；对外输出通道构造时注入。
插件不能 import `core.event` / `api` / `persistence`（import-linter 检查）。

## 设计问题

审阅中发现、尚未拍板的问题记在 [docs/open-questions.md](docs/open-questions.md)，决定后移到「已决」。
