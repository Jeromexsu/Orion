# 术语表

代码与讨论中统一使用的叫法。新定下的术语在这里补充；有歧义时以这里为准。

## 目标与数据（target / collector）

| 术语 | 代码 | 含义 |
|---|---|---|
| 目标类型 | `Target` 的子类（如 `Aircraft`） | 一类静态目标，如飞机。由开发者用代码定义：`@target_type(类型名, observed_points=[...])` 声明类型名和可以在哪些观察点被观测，字段用 `provides(查询键)` 关联查询键 |
| 目标 | `Target` 子类的实例 | 一个具体的静态目标，如注册号 B-2447 的那架飞机 |
| 观察点 | `ObservedPoint` 的子类（如 `Position`），名字如 `position` | 名字 + 它返回什么观测（`observation`）。与目标类型无关，多种目标类型可共用 |
| 观测（observation） | `Observation` 的子类（如 `PositionObservation`） | 观察点观察之后返回的数据本身，字段就是观测的形状，如 `lat`、`lon` |
| 查询键 | `QueryKey` 的子类（如 `Icao24`） | 拿什么去查一个目标：名字 + 取值的类型与格式。与观察点对称——观察点是输出契约，查询键是输入契约 |
| 查询方式 | `UpstreamAdapter.query_key_sets` 的一项 | 一组联立的查询键；目标能提供这组里的全部查询键，就能用这种方式查。UpstreamAdapter 只能拿到查询键范围内的目标信息 |
| 上游 | `upstream`（名字，如 `opensky`） | 一个外部数据提供方，可以服务多个观察点；按名字标识，订阅、游标、路由都用这个名字 |
| 上游适配器 | `UpstreamAdapter` 的子类（如 `OpenSkyAdapter`） | 接入一个上游的插件，`name` 就是上游名：声明服务哪些观察点（`observed_points`）、支持哪些查询方式（`query_key_sets`）；把查询键翻译成上游 API 的参数（如 `Icao24` → `ICAO`），把上游响应翻译成观测 |
| 可观测目标（obs） | `ObservableTarget` | 封装好的「具体目标 + 一个观察点」，ID 形如 `t1:position`；持有全部可用上游（服务该观察点且目标能提供其某种查询方式的上游）和订阅关系，全局唯一，由 `TargetManager` 创建 |
| 订阅 | `ObservableTarget.subscribe(订阅者, 上游集合)` | 订阅者指定要哪些上游；可观测目标按上游把数据路由给订阅者 |
| 发布 | `ObservableTarget.publish(观测外壳)` | 可观测目标把一条观测推给订阅了其上游的订阅者，逐个隔离异常；collector 采集后调用 |
| 观测外壳 | `ObservationEnvelope` | 一次观测连同来源信息：`observable_id`、`upstream`、`observation`（观测实例）、`occurred_at`、`source_id`、`raw`。collector 产出，在采集 → 分发 → 条件判断的管道里流动 |

注意区分 **obs**（可观测目标，长期存在的对象）、**observation**（观测，观察点返回的数据）与 **envelope**（观测外壳，观测加来源信息）。「动态数据」一词已不再使用。

## 事件（event）

| 术语 | 代码 | 含义 |
|---|---|---|
| 父事件 | `ParentEvent` | 静态：目标命名空间（target_id 集合）+ 模板集合 + `digest()`；自己不订阅 |
| 模板 | `EventTemplate`（定义为 `TemplateDef`） | 静态、不可变、带版本：可观测目标声明、开启条件、规则、算子挂载 |
| 可观测目标声明 | `ObservableDef` | 模板要观测的 (target_id, observed_point) 及订阅哪些上游 |
| runner | `EventRunner` | 运行中的模板：按可观测目标声明订阅，评估开启条件，管理子事件生命周期（开启、换版本、存档） |
| 子事件 | `Event` | 模板的一次运行（一个周期）；同一模板同时最多一个 |
| 周期 | `cycle` | 子事件的周期标识：触发开启的那条数据发生的年份。子事件是以年为周期重复发生的事情 |
| 开启条件 | `open_condition_def` / `EventTemplate.open_tree` | 无活跃子事件时命中才开新子事件 |
| 规则 | `RuleDef` / `CompiledRule` | 子事件运行期间逐条评估的条件，命中时触发挂在它上面的算子 |
| 算子 | `Operator`（用 `@operator` 声明） | 挂在子事件生命周期上的动作；按「作用域 × 是否提建议」声明能做什么 |
| 作用域 | `Scope`：`external` / `event` / `parent` / `target` | 算子影响哪一块。直接作用只开放 `external`（系统外部）和 `event`（子事件）；`parent`（父事件）/ `target`（目标）只能提建议 |
| 提建议 | `proposes=True` → `ctx.propose(...)` | 交给 hil，分析师确认后才执行；影响哪个作用域由提议的动作决定 |
| 挂载 / 钩子 | `OperatorMountDef`（定义）/ `Hook`（编译后） | 在某个挂载点挂一个算子，带参数；编译成持有算子实例和有类型参数的 `Hook` |
| 调用时机 | `Occasion`（`CreatedOccasion` / `ObservationOccasion` / `RuleHitOccasion` / `StatusUpdatedOccasion` / `ClosedOccasion`） | 算子为什么被调用：在哪个挂载点、当时发生了什么 |
| 算子上下文 | `OperatorContext` | 算子运行时拿到的：参数、只读信息，以及声明过的能力（`ctx.event`、`ctx.propose`） |

## 条件（condition_engine）

| 术语 | 代码 | 含义 |
|---|---|---|
| 条件定义 | `ConditionDef`（`LeafDef` / `BranchDef`） | 纯数据，可任意嵌套；两种节点都是 `kind` + `op` + 操作对象 |
| 条件树 | `ConditionTree`（`LeafNode` / `BranchNode`） | 编译后的条件；`evaluate(envelope, state)` 是纯函数，状态由调用方保管 |
| 判断方式 | `Evaluator` | 唯一的扩展点；继承 `Evaluator[判定标准模型]`，用 `@evaluator(requires=...)` 声明（`op` 默认类名首字母小写，叶子的 `op` 引用它），实现 `evaluate(observation, occurred_at, state, criteria)`：拿这条观测（及发生时间）和上一轮状态对照判定标准，拿不到来源信息 |
| 节点路径 | `path`（如 `root/1/0`） | 节点在树中的地址；用于定位编译错误、按叶子分组状态、审计追溯 |

## 命名约定

- 纯数据定义的类型以 `Def` 结尾；装着 `Def` 的字段 / 参数以 `_def` / `_defs` 结尾；运行时对象不带后缀。
- 注册表类型的依赖叫 `*_registry`（只有一个注册表依赖的类内部简写 `registry`），不用复数。
