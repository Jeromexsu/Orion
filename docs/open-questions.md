# 待决设计问题

审阅过程中发现、尚未拍板的问题。决定后在对应条目写明结论并移到「已决」。

## 待决

### 1. 子事件模型的遗留项

第 1 条主体已决并实现（见「已决」），剩余：
- 关闭条件是否在模板里显式声明（现沿用 `status["closed"]` 约定；年度事件「何时算结束」是关键问题）。

### 2. `ObservableTargetRepository` 是否保留

它按文档第九节返回 `ObservableTarget` 活对象；`TargetManager` 只在创建时写入、删除目标时移除，
从未读取——重启恢复靠 event 模块重新订阅。选项：保留 / 改为存纯数据记录 / 去掉。
**状态**：等审阅到 `core/target/repository.py` 和 `manager.py` 时决定。

### 3. UpstreamAdapter 与 Target 子类的对应关系只靠约定

**已解决**：观察点与目标类型解耦后，UpstreamAdapter 不再引用目标类型（见「已决 · 观察点」）；查询也不再靠字段名
约定（见「已决 · 查询键」）。`UpstreamAdapter` / `Operator` 已改为基类，注册时检查类属性声明；UpstreamAdapter 直接构造
观测实例，collector 检查其类型。剩余可做的是 UpstreamAdapter 契约测试基类（跑一次 fetch，检查 source_id 不重复、
since 之前的不返回），等往外分插件任务时再搭。

### 4. 跨目标条件：单个叶子只能看一个目标的数据

**发现于**：审阅 condition_engine 的 `Evaluator` 时。**状态**：待讨论。

每个叶子条件只绑定一个可观测目标，`evaluate(observation, occurred_at, state, criteria)` 每次只拿到一条观测；
`LeafNode` 对不属于自己目标的数据直接返回「不适用」。因此需要同时比较多个目标数据的条件——
如「两架飞机相互接近」「A 在 B 之前进入区域」——单个叶子做不了。组合节点（all/any/not）只组合
各叶子的三值结果，也拿不到对方的数值。

可能的做法：
1. 多目标判断方式：允许某种 `Evaluator` 绑定多个目标，每来一条数据把该目标的最新值记进自己的
   state，再用各目标的最新值判断（需要改 `LeafDef.observable` 为多个可观测目标、`LeafNode` 的适用性判断）；
2. 在组合层面引入跨叶子比较：新的节点类型，读取子叶子 `extracted` 出来的数值做比较；
3. 派生可观测目标：在 collector / target 层把「两机距离」做成一个派生的观察点，条件照旧单目标。

**影响范围**：`condition_engine/definitions.py`（LeafDef）、`condition_engine/tree.py`（LeafNode）、判断方式插件接口；
方案 3 则主要在 target / collector。

### 5. 条件引擎依赖 target 的前提（观察项）

**状态**：暂维持现状，满足触发条件时重新评估。

条件引擎依赖 target，只依赖一个数据类型 `Observation`（不碰 `TargetManager`、`ObservableTarget`）。维持的理由：
`LeafDef.observable` 本就是可观测目标 ID，条件在概念上就是「对可观测目标的观测做判断」，原 Protocol 只是把
这层关联藏了起来；target 是最底层、最稳定的模块，无环；回退只需在条件引擎内重新引入输入 Protocol。

代价：条件引擎与「观测」的形状绑定；判断方式只拿观测和发生时间（`evaluate(observation, occurred_at, state, criteria)`），来源信息不交出去；
`Observation` 的变更会波及条件引擎和判断方式插件；与设计文档「条件引擎零依赖」不一致。

**触发重新评估的条件**：出现要判断「非观测类输入」的需求（如一段新闻文本、一条人工录入的线索，
设计文档 `EvalResult.extracted` 提到的「命中的关键词、地点」可能属于此类）。届时条件引擎应改回
定义自己的输入 Protocol，依赖不再指向 target。

### 6. 观测外壳的持久化

`ObservationEnvelope.observation` 持有具体观测实例（如 `PositionObservation`），序列化时按实际类型输出
（`SerializeAsAny`）。从存储读回时需要先知道是哪个观察点，才能还原成对应的观测类——与 `Target` 子类的
还原类似，需要按 `observable_id` 找到观察点再 `model_validate`。持久化层实现时处理；
`ObservationRepository` 目前只定义了接口。

### 7. 手动开启子事件

**状态**：待讨论。

现在只能手动**结束**一个周期（`EventRunner.close_active`），不能手动**开启**：子事件只在开启条件命中时
由 runner 自动创建。对年度事件，分析师可能需要「开启条件还没命中，但判断今年这次已经开始」的强制开启。

可能的做法：给 runner 加 `open_manually(reason, cycle)`，在没有活跃子事件时直接开一个，跑 `created` 钩子；
待定点——
- 没有触发数据：`cycle` 由谁给（分析师指定 / 取当前年份），开启时的第一条观测从哪来（等下一条观测到来再处理）；
- 已有活跃子事件时拒绝还是忽略；
- 是否也开放给 hil（校正类算子提议「开启本周期」，经分析师确认），即加入白名单动作；
- 记录谁、为什么手动开启，便于审计。

### 9. 可观测目标的可用上游是快照，会过时

**发现于**：审阅 `ObservableTarget.__init__` 时。**状态**：已记下，暂不改。

可观测目标创建时由 `TargetManager` 问 `UpstreamCatalog` 得到可用上游，之后不再刷新：

| 之后发生的事 | 现在的表现 |
|---|---|
| 目标记录更新，不再能提供某上游要的查询键 | 仍留在 `upstreams` 里；collector 采集时 `choose_query` 为 None，每轮记一条警告并跳过 |
| 目标记录更新，新能提供某上游要的查询键 | 新可用的上游**不加进来**，模板订阅它会被拒绝；要等重启重建可观测目标 |
| 运行中注册了新的上游适配器 | 同上（目前 bootstrap 启动时一次注册完，尚不会发生） |

可能的做法：`TargetManager.upsert_target` 在 `rebind_target` 时重新问 `UpstreamCatalog`，刷新 `upstreams`——新可用的加进来；
不再可用的移出，已有的订阅关系保留（collector 只采集「可用且有人订阅」的上游，自然停采，目标记录恢复后自动恢复）。
改动只在 `upsert_target` / `rebind_target` 两处。

### 10. 判断方式的 `requires` 靠字段名对齐观测

**发现于**：审阅 `OnEnter` 时。**状态**：已记下，暂不改；出现第二个观察点并需要复用同一判断方式时再做。

`Evaluator.requires` 是字段名字符串（如 `{"lat", "lon"}`），编写者得知道观测里字段恰好叫这个名字。写错不会静默——
模板编译时报 `lacks fields`——但不同观察点对同一语义命名不同（`lat` / `latitude`）时，判断方式无法复用。

可能的做法：仿照查询键，用观测的公共基类表达「能力」：

```python
class HasPosition(Observation):          # 能力：有经纬度
    lat: float
    lon: float

class PositionObservation(HasPosition): ...
class OnEnter(Evaluator[...]):
    requires = HasPosition               # 要求一个类，不是一串字段名
```

编译时改为 `issubclass(观测类, HasPosition)`，靠 import 对齐；判断方式里可把观测当 `HasPosition` 用，类型检查器看得懂。
待定点：
- 能力怎么划分（位置、高度、速度……），划错了改起来费事；
- 通用型判断方式（如「某字段大于某值」）字段名在判定标准里，需另加编译时检查（判定标准里的字段存在于观测类）；
- 可为空字段（`altitude_m: float | None`）继承只保证「有这个字段」，运行时「为空则不适用」的检查仍要保留。

### 11. 按上游调整判断的可信度

**发现于**：收窄 `Evaluator.evaluate` 签名时（不再传观测外壳）。**状态**：已记下，有需要时再做。

需求：不同上游可信度不同（如雷达不如 ADS-B），同样判为「命中」，可信度应当打折。

不放进判断方式：判断方式按上游调整就得写 `if upstream == "radar"`——条件插件认识上游插件的名字（跨插件字符串耦合），
且每个判断方式各写一遍、口径不一。判断方式因此只拿观测和发生时间，拿不到上游。

可能的做法：上游可信度作为独立的一层——

```python
@upstream_adapter(observed_points=[Position], query_key_sets=[{Icao24}], confidence=0.6)
class RadarAdapter(UpstreamAdapter): ...
```

叶子节点在判断方式返回后，把判断方式给的可信度与这条观测来源上游的可信度合并（如相乘）。
待定点：
- 可信度由上游适配器声明，还是在模板里按（可观测目标, 上游）配置，或两者都有（模板覆盖默认）；
- 合并方式（相乘 / 取小）；组合节点（all / any）对可信度的合并规则是否要随之调整；
- 同一观察点的不同观测（如有无高度）是否也影响可信度。

### 12. 算子挂载编译后仍是纯数据

**发现于**：审阅 `TemplateCompiler._bind` 时。**状态**：看完 operators 模块后与算子写法、上下文传参一起改。

编译只校验挂载并把 `params` 规范化（校验后 `model_dump()` 回 dict），结果仍是 `OperatorMountDef`。与条件一侧不对称：

| | 条件（叶子） | 算子挂载 |
|---|---|---|
| 编译结果 | `LeafNode`：持有判断方式实例 + 有类型的 `criteria` | 仍是 `OperatorMountDef`，`params` 是 dict |
| 运行时找插件 | 已持有 | 每次 `operator_registry.get(name)` |
| 运行时拿参数 | 有类型的实例 | dict，算子自己再 `model_validate` 一次 |

另外 `CompiledRule.hook_defs`、`EventTemplate.hooks_at` 是运行时对象里装着 Def，违反命名约定。

可能的做法：编译成运行时对象 `Hook`（算子实例 + 有类型的参数 + 挂载点）；`Event._run_hooks` 直接用 `hook.operator`，
算子的 `run` 拿到有类型的参数。

同一批要一起定的：
- **`Trigger` 按挂载点分类型**：现在除 `mount_point` 外的 `envelope` / `result` / `patch` 都是「可能为 None」，
  哪个有值取决于挂载点，算子得自己记住并断言（如 `assert trigger.envelope is not None`）。可改为可辨识联合：
  `CreatedTrigger` / `ObservationTrigger`（pre、post：envelope）/ `RuleHitTrigger`（envelope + result）/
  `StatusUpdatedTrigger`（patch）/ `ClosedTrigger`，以 `mount_point` 区分；算子 `match` 后字段类型确定，
  只挂 `rule_hit` 的算子可直接声明只收 `RuleHitTrigger`。
- **`Trigger` 改名 `Occasion`**（已定）：它只是一条记录——算子这次在哪个挂载点、因为什么被调用，附带当时的数据；
  「trigger」听起来像会触发动作。按挂载点分类型后为 `CreatedOccasion` / `ObservationOccasion` / `RuleHitOccasion` /
  `StatusUpdatedOccasion` / `ClosedOccasion`；`run(occasion, ctx)`。
- **`Category` / `Level` / `MountPoint` 挪到 `operator.py`**（已定）：它们描述算子是什么、能挂在哪，现在放在 `trigger.py`。
- 算子是否也改为装饰器声明（`@operator(...)`）；上下文里的 `params` 怎么传。

### 8. 其他（随审阅推进逐条确认）

- 模板 ID 全局还是按父事件区分（现为全局：`TemplateRepository` 只按 template_id 存取）。
- `EvalResult.outcome`、`Draft.status` 的中文字面值是否对外改为英文枚举。
- 父事件级算子挂载由什么触发。
- 校准钩子的挂载点（设计文档待办）。
- 异步输出算子：`Operator` 加异步标记，依赖队列选型（Celery+Redis vs arq）。
- `SubEventSlot.on_data()` 中实例 `process()` 中途异常：内存里的实例状态已部分改动但未存库，内存与库不一致。
- report 模块是否开 pyright strict。
- 设计文档第八、九节与代码同步。

## 已决

- **条件引用范围：event 决定范围，条件编译器按范围检查**（审阅 `_compile_leaf` 时讨论，不把范围检查挪到模板编译器）：
  模板编译器根据可观测目标声明组装 `declared_observables`（范围 + 每个的观测类），条件编译器对每个叶子做一次查找，
  同时完成「引用的可观测目标在不在范围里」和「观测有没有判断方式要的字段」。像编译器按调用方给的符号表检查标识符。
  挪到模板编译器的代价：要重新遍历条件树收集叶子引用（即已删除的 `observables()`）；条件编译器取观测类时仍得处理
  「查不到」，范围检查变成两处；错误失去节点路径。条件编译器不知道「模板」，只知道「给定的可引用清单」。

- **条件节点统一为 kind + op + 操作对象**：`OpDef` / `OpNode` → `BranchDef` / `BranchNode`（`kind: "branch"`）；叶子的
  `type` → `op`（引用 `Evaluator.op`，原 `Evaluator.type`，顺带去掉了遮蔽内置 `type` 的写法）；条件留痕的 `"type"` 键 → `"op"`。
  叶子的参数叫 `criteria`（判定标准），`Evaluator.evaluate(observation, occurred_at, state, criteria)`（后又收窄：不再传观测外壳）；算子挂载的 `params` 不变。

- **条件状态：结果直接给新状态，不给补丁**：`EvalResult.state_patch` 改为 `state`，含义在两层一致——「求值对象的新状态，
  `None` 表示没变」：判断方式返回本叶子的完整新状态，`ConditionTree.evaluate` 返回整棵树的新状态。`apply_state_patch`
  不再对外；调用方（runner、`Event`）不再合并，直接换上，变了才持久化。状态仍放在树外、由调用方保管——树被一个模板版本
  历年的所有子事件共用。

- **模板编译创建可观测目标的时机**：`TemplateCompiler` 先只检查（`TargetManager.inspect_observable`，不创建），
  全部通过后才 `get_observable` 取得 / 创建，所以被拒绝的模板不留下可观测目标。编译成功的模板持有确定的
  可观测目标（`compiled_observables`）；挂起的新版本因此会在切换前就创建出暂时无人订阅的可观测目标——
  它们不被采集、代价很小，与「取消订阅后可观测目标保留到目标删除」的生命周期一致，接受这一点，
  不改为 runner 订阅时再延迟创建。

- **观测 / 观察点 / 外壳三分**（取代「观测与动态数据合一」）：
  - `Observation` 子类（如 `PositionObservation`）= 观察点观察之后返回的数据，字段即形状；
  - `ObservedPoint` 子类（如 `Position`）= 名字 + `observation`（返回什么观测），普通类、不实例化；
  - `ObservationEnvelope` = 外壳：来源信息 + 具体观测实例，在管道里流动；持久化是后面单独的问题（见第 6 条）；
  - 条件树与判断方式接收外壳，判断方式按字段名读 `envelope.observation`，`requires` 字段须有值否则不适用；
  - 条件引擎依赖 target（`ObservationEnvelope`），无环；「动态数据」一词不再使用。
- **条件引擎不再查询 target**：去掉设计文档的 `TargetResolver`。`ConditionCompiler.compile(condition_def, declared_observables)`
  由调用方传入「可观测目标 ID → 它产出的观测类」，字段由观测类自己描述（原为调用方拼好的字段名集合）；`EventTemplate.compile()` 按可观测目标声明向 `TargetManager`
  解析（目标、观察点存在，上游可用）并提取字段，所以条件只能引用已声明的观测、判断方式需要的字段必须存在。
  文档时代模板没有可观测目标声明，条件引擎只能自己去问 target；有了可观测目标声明，调用方手里已有这份信息。

- **静态定义与运行时对象的命名约定**：纯数据定义的类型以 `Def` 结尾（`TemplateDef`、`RuleDef`、
  `ObservableDef`、`OperatorMountDef`）；装着 `Def` 的字段以 `_def` / `_defs` 结尾（`observable_defs`、
  `open_condition_def`、`rule_defs`、`hook_defs`、`condition_def`）；运行时对象不带后缀（如
  `EventTemplate.open_tree`、`EventTemplate.rules` 返回的 `CompiledRule`）。条件引擎契约
  `LeafDef` / `OpDef` 的 `children` 按设计文档第八节照抄，不改。（后来 `OpDef` 改名 `BranchDef`，见下条「条件节点统一」。）

- **持久化归管理者**：谁管理一组对象谁负责存它们——`ParentEventManager` 存父事件记录（仓库从
  `ParentEventServices` 移到 manager 的构造参数），`EventRunner` 存子事件记录；`ParentEvent` 和 runner
  只在变更后调用 `on_change` 通知上一层，自己不碰自己的仓库。
- **依赖按具体类型命名**：构造参数、依赖字段一律用类型名的 snake_case，不用复数名词或抽象称呼——
  `TargetManager` → `target_manager`、`TemplateRepository` → `template_repository`、
  `EvaluatorRegistry` → `evaluator_registry`、`UpstreamCatalog` → `upstream_catalog`。
  接口类型按接口名（`SuggestionSink` → `suggestion_sink`，实际装的是 `HilManager`）。
  `bootstrap.Repositories` / `App` 的字段同样处理。
- **event 模块命名**：`ParentEvent` 不变；`SubEventSlot` → `EventRunner`，`SubEventTemplate` →
  `EventTemplate`，`SubEventInstance` → `Event`（子事件）。随之：`InstanceRecord` / `InstanceRepository` /
  `InstanceClosedError` → `EventRecord` / `EventRepository` / `EventClosedError`；`SlotStateRepository` →
  `RunnerStateRepository`；`EventManager` → `ParentEventManager`（它管的是父事件）；算子层级 `Level`
  取值 `"instance"` → `"event"`，上下文 `instance_id` → `event_id`。下文历史条目里的 slot / 实例
  即 EventRunner / Event。
- **叶子字段命名**：设计文档第八节的 `LeafDef.target` → `observable`（填的是可观测目标 ID，如 `t1:position`，
  不是静态目标 ID）；`ConditionTree.targets()` → `observables()`（后删除：引用范围在编译时已查完，无人使用）；trace 键 `target` → `observable`。
- **判断方式命名**：设计文档的 `LeafConditionEvaluator` / `LeafEvaluator` → `Evaluator`（唯一的可扩展判断方式，
  与 `EvaluatorRegistry` 对应；「挂在叶子上」由 `LeafNode` 表达）。

- **子事件模型（原第 1 条，已实现）**：保留模板。
  - 父事件（静态）：静态目标命名空间（target_id 集合）+ 静态模板集合 + `digest()`；不订阅任何东西。
  - 模板（静态、不可变、带版本）：可观测目标声明（目标 + 观察点 + 上游）、开启条件（必填）、规则、算子挂载。
    条件树引用的可观测目标必须在可观测目标声明里；观测的目标必须在父事件命名空间里；上游在装入时检查可用。
  - slot（运行时，每个模板一个）：按可观测目标声明订阅，自己就是订阅者；每条数据都评估开启条件并持久化其状态；
    无活跃实例且开启条件命中时开实例并把该条数据交给它；同一模板最多一个活跃实例。
  - 换版本（方案 a）：新版本只对下一个周期生效——有活跃实例时挂起（`pending_version`），实例关闭后切换、
    重新订阅、开启条件状态清空；无活跃实例时立即切换。
  - 实例记录加周期标识 `cycle`（触发开启那条数据发生的年份）。
  - 业务背景：子事件是以年为周期重复发生的事情，实例可能持续数周到数月。

- **数据定义放哪**：每个定义回到所属模块，不设公共 contracts 包（曾经设过，后撤销）。
  `LeafDef` / `OpDef` / `ConditionDef` / `EvalResult` → condition_engine；`QuerySpec` / `DynamicData` → target；
  `Trigger` / `Category` / `Level` / `MountPoint` → operators；`Suggestion` / `Proposal` → hil；`Draft` → report。
  代价：operators 由设计文档的「零依赖」改为依赖 target / condition_engine / hil（均不反向依赖它，无环）。
- **目标类型写法**：去掉 `TargetType`，每种目标类型继承 `Target` 基类；目标类型只由开发者通过代码定义。
- **观察点（取代「关注点」与「动态数据 schema」）**：观察点与目标类型解耦，不同目标类型可共用。
  - `ObservedPoint` 子类（如 `Position`）就是观测 `fields` 的 schema，放在 `plugins/observed_points/`；
  - 目标类型用 `observed_points` 声明可以在哪些观察点被观测（取代原 `focuses`）；
  - UpstreamAdapter 声明 `observed_points`（服务哪些观察点）和支持的查询方式（见下条「查询键」），不再引用目标类型；
    上游 = 数据提供方，一个上游可服务多个观察点，`fetch` 按 `observed_point` 分支；查询方式对它服务的
    全部观察点通用（真遇到按观察点不同再扩展成按观察点声明）；
  - `ObservableTarget(target, observed_point, upstreams)`；`ObservableDef.observed_point`
    存观察点名；`TargetManager` 从已注册目标类型收集观察点，重名报错。
- **查询键（取代「同名属性字段含义一致」的约定）**：查询的输入也要有人负责，与观察点对称。
  - `QueryKey` 子类（如 `Icao24`）= 名字 + 取值的类型与格式，放在 `plugins/query_keys/`；
  - 目标类型在提供它的字段上关联：`icao24: str | None = provides(Icao24, default=None)`；构造目标时按查询键校验取值；
  - UpstreamAdapter 声明 `query_key_sets`（支持的查询方式：多组查询键，按优先级）；按查询键类匹配，不看字段名；
    采用目标能提供的第一种，组装成 `query`（查询键 → 取值）；
  - 不在查询键范围内的，UpstreamAdapter 拿不到：去掉 `QuerySpec`（目标属性、别名、目标类型兜底都不再传），
    `UpstreamAdapter.fetch(observed_point, query, since)`——查什么、凭什么查、从哪儿开始查；别名要用来查就定义成查询键；
  - 挑查询方式是基类方法 `UpstreamAdapter.choose_query(目标能提供的查询键)`，只接收查询键、不接收目标本身；
    判断可用上游和实际采集都用它，保证一致；
  - 一种查询方式可以联立多个查询键（`frozenset({B, C})`），缺一个就不满足、退到下一种。
- **插件接口用基类，不用协议**：`UpstreamAdapter`、`Operator` 与 `Evaluator` 一样是 ABC 基类，类属性的类型在基类里
  声明，插件直接赋值（`category = "progress"`），不必逐个标注，也不会踩「协议是只读属性、pyright 不认 ClassVar」的坑；
  注册时检查类属性是否都声明了。`FetchedRecord` 直接装观测实例（原为字段 dict），字段写错在 UpstreamAdapter 里当场报错。
- **声明用装饰器**：目标类型、观察点、查询键都用装饰器声明（`@target_type` / `@observed_point` / `@query_key`），
  字段关联查询键用 `provides(...)`，插件作者不必写 `ClassVar` / `Annotated` / `Literal`；`type` 字段由类型名自动填写；
  `Target` 的不可变写在 `model_config` 里，子类不必重复 `frozen=True`。装饰时就检查声明，写错在 import 时报错。
- **上游归属**：可观测目标的上游列表由 `TargetManager` 问 `UpstreamCatalog` 得到，不由外部传入；
  订阅者 subscribe 时指定要哪些上游，可观测目标内部按上游路由。
