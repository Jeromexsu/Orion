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
- 按职责给类起名：
  - `*Manager`：管数据——运行期间不断变化、要存库的业务数据的生命周期，不只是增删改查，还有状态流转和规则
    （如「有订阅者不能删目标」「已发出的报告不能改」）。它是有自己数据的模块的入口，仓库注入在它身上，用仓库存取；
    规则在 manager 里，不在仓库里（`TargetManager` 管目标实例，`ParentEventManager`、
    `HilManager`、`ReportManager`）。没有自己数据的模块没有 manager。入口做的事能用一个动词说清时可以用动词名词化（`Collector`）。
  - `*Registry`：管插件——数据（模板 JSON、库里的记录）里只有名字，注册表把名字变回写框架时还不知道的插件。
    要不要注册表只看数据里会不会出现它的名字，以及能不能在上下文里解析：查询键只在代码里按类引用，所以没有；
    观察点在模板里按名字引用，但总和目标成对出现，在那个目标类型的 `observed_points` 里找就够了，所以也没有。一种插件的注册表只有 `register` / `get` / 列出全部（外加注册时的声明检查）；启动时由
    bootstrap 注册，之后只读，注入给用它的一方。按它装的东西命名：目标类型的插件是类（`Aircraft`），所以叫
    `TargetTypeRegistry`，不叫 `TargetRegistry`（目标是这些类的实例，是数据，归 `TargetManager`）；其余插件是实例
    （`UpstreamAdapterRegistry`、`EvaluatorRegistry`、`HookRegistry`）。
  - `*Factory`：纯运行时、不存库的单例工厂——按键取共享实例，没有就创建（享元模式的 FlyweightFactory），
    如 `ObservableTargetFactory`。不存库、没有生命周期的东西不叫 manager。
  - `*Repository`：只管数据怎么存取，协议定义在 core，由 repo 层实现。协议和它收发的持久化记录（`*Record`）是同一份契约，
    放在同一个 `repository.py` 里（端口 + 它的数据类型）。活对象和记录之间的转换成对命名：`to_record()` / 类方法 `from_record(record, ...)`；
    领域代码只在这两处碰记录，要从历史里查东西就给仓库加一个窄的查询（如 `count_closed`），不把整批记录交出去。
  - `*Compiler`：把纯数据定义编译成运行时对象，无状态（`TemplateCompiler`、`ConditionCompiler`、`MountCompiler`）。
- 行为类用普通类，跨 JSON 边界的纯数据用 Pydantic，不用 dataclass。
- 有「定义 → 编译 → 运行时对象」的模块按阶段分文件：`definitions.py`（纯数据 `*Def`，不依赖任何运行时对象）、
  `compiler.py`（`*Compiler`）、运行时产物各自的文件（如 condition_engine 的 `tree.py`、event 的 `template.py`、hooks 的 `mount.py`）。

## 插件

目标类型、观察点、查询键、判断方式、上游适配器、钩子都用装饰器声明（`@target_type` / `@observed_point` / `@query_key` /
`@evaluator` / `@upstream_adapter` / `@hook`，字段用 `provides(...)`）。判断方式同时继承 `Evaluator[判定标准模型, 观测类]`（要求一个观测类，不写字段名），
`op` 默认类名首字母小写；上游适配器继承 `UpstreamAdapter`，上游名默认类名去掉 Adapter 后缀、首字母小写。
钩子继承 `Hook[参数模型]` 并用 `@hook(mount_points={MountPoint.RULE_HIT}, scopes={Scope.EVENT}, proposes=...)` 声明
（挂载点、作用域是 `StrEnum`，代码里用成员、不写字符串；模板 JSON 里仍是字符串值），`name` 默认类名首字母小写；
直接作用只能是 `external` / `event`，父事件和目标只能提议（`proposes=True`）；对外输出通道构造时注入。
插件不能 import `core.event` / `api` / `persistence`（import-linter 检查）。

## 设计问题

审阅中发现、尚未拍板的问题记在 [docs/open-questions.md](docs/open-questions.md)，决定后移到「已决」。
