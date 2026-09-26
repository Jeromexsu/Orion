# 待决设计问题

审阅过程中发现、尚未拍板的问题。决定后在对应条目写明结论并移到「已决」。

## 待决

### 1. 子事件模型的遗留项

第 1 条主体已决并实现（见「已决」），剩余：
- 关闭条件是否在模板里显式声明（现沿用 `status["closed"]` 约定；年度事件「何时算结束」是关键问题）。

### 2. `ObservableTargetRepository` 是否保留

它按文档第九节返回 `ObservableTarget` 活对象；`TargetManager` 只在创建时写入、删除目标时移除，
从未读取——重启恢复靠 event 模块重新 acquire。选项：保留 / 改为存纯数据记录 / 去掉。
**状态**：等审阅到 `core/target/repository.py` 和 `manager.py` 时决定。

### 3. Adapter 与 Target 子类的对应关系只靠约定

**状态**：理顺 collector 时处理。

Adapter 开发者必须和 `Target` 子类对上：`serves` 里的 (类型名, 关注点)、`spec.attributes` 里的属性字段、
返回的 `FetchedRecord.fields` 要符合该关注点的 schema。现在全是字符串和 dict：`serves` 拼错不报错
（Adapter 永远不被选中）；`spec.attributes["..."]` 无静态检查；`fields` 不合 schema 要到 collector
校验才发现，且只记警告、丢弃记录。

**建议**（插件之间可以互相 import）：
1. `serves` 直接写类，如 `{(Aircraft, "position")}`，注册 Adapter 时校验关注点存在；
2. 提供辅助函数把 `spec` 还原成 `Aircraft` 实例，Adapter 里写 `target.registration` 有静态检查；
3. `fields` 用 schema 类构造，如 `AircraftPosition(lat=..., lon=...)`；
4. Adapter 契约测试基类：检查 `serves` 合法、`fields` 通过 schema、`source_id` 不重复。

**背景**：target 与 collector 耦合较紧。core 层面是单向的（collector 依赖 target；target 只通过
`UpstreamCatalog` Protocol 知道「上游」这个概念），但插件层面 Adapter 与 Target 子类是成套开发的。

### 4. 跨目标条件：单个叶子只能看一个目标的数据

**发现于**：审阅 condition_engine 的 `Evaluator` 时。**状态**：待讨论。

每个叶子条件只绑定一个可观测目标，`evaluate(params, fields, state)` 每次只拿到一条数据的 `fields`；
`LeafNode` 对不属于自己目标的数据直接返回「不适用」。因此需要同时比较多个目标数据的条件——
如「两架飞机相互接近」「A 在 B 之前进入区域」——单个叶子做不了。组合节点（all/any/not）只组合
各叶子的三值结果，也拿不到对方的数值。

可能的做法：
1. 多目标判断方式：允许某种 `Evaluator` 绑定多个目标，每来一条数据把该目标的最新值记进自己的
   state，再用各目标的最新值判断（需要改 `LeafDef.target` 为多目标、`LeafNode` 的适用性判断）；
2. 在组合层面引入跨叶子比较：新的节点类型，读取子叶子 `extracted` 出来的数值做比较；
3. 派生可观测目标：在 collector / target 层把「两机距离」做成一个派生的关注点，条件照旧单目标。

**影响范围**：`condition_engine/definitions.py`（LeafDef）、`condition_engine/tree.py`（LeafNode）、判断方式插件接口；
方案 3 则主要在 target / collector。

### 5. 其他（随审阅推进逐条确认）

- 模板 ID 全局还是按父事件区分（现为全局：`TemplateRepository` 只按 template_id 存取）。
- `EvalResult.outcome`、`Draft.status` 的中文字面值是否对外改为英文枚举。
- 父事件级算子挂载由什么触发。
- 校准钩子的挂载点（设计文档待办）。
- 异步输出算子：`Operator` 加异步标记，依赖队列选型（Celery+Redis vs arq）。
- `SubEventSlot.on_data()` 中实例 `process()` 中途异常：内存里的实例状态已部分改动但未存库，内存与库不一致。
- report 模块是否开 pyright strict。
- 设计文档第八、九节与代码同步。

## 已决

- **静态定义与运行时对象的命名约定**：纯数据定义的类型以 `Def` 结尾（`TemplateDef`、`RuleDef`、
  `ObservationDef`、`OperatorMountDef`）；装着 `Def` 的字段以 `_def` / `_defs` 结尾（`observation_defs`、
  `open_condition_def`、`rule_defs`、`hook_defs`、`condition_def`）；运行时对象不带后缀（如
  `EventTemplate.open_tree`、`EventTemplate.rules` 返回的 `CompiledRule`）。条件引擎契约
  `LeafDef` / `OpDef` 的 `children` 按设计文档第八节照抄，不改。

- **event 模块命名**：`ParentEvent` 不变；`SubEventSlot` → `EventRunner`，`SubEventTemplate` →
  `EventTemplate`，`SubEventInstance` → `Event`（子事件）。随之：`InstanceRecord` / `InstanceRepository` /
  `InstanceClosedError` → `EventRecord` / `EventRepository` / `EventClosedError`；`SlotStateRepository` →
  `RunnerStateRepository`；`EventManager` → `ParentEventManager`（它管的是父事件）；算子层级 `Level`
  取值 `"instance"` → `"event"`，上下文 `instance_id` → `event_id`。下文历史条目里的 slot / 实例
  即 EventRunner / Event。
- **判断方式命名**：设计文档的 `LeafConditionEvaluator` / `LeafEvaluator` → `Evaluator`（唯一的可扩展判断方式，
  与 `EvaluatorRegistry` 对应；「挂在叶子上」由 `LeafNode` 表达）。

- **子事件模型（原第 1 条，已实现）**：保留模板。
  - 父事件（静态）：静态目标命名空间（target_id 集合）+ 静态模板集合 + `digest()`；不订阅任何东西。
  - 模板（静态、不可变、带版本）：观测声明（目标 + 关注点 + 上游）、开启条件（必填）、规则、算子挂载。
    条件树引用的可观测目标必须在观测声明里；观测的目标必须在父事件命名空间里；上游在装入时检查可用。
  - slot（运行时，每个模板一个）：按观测声明订阅，自己就是订阅者；每条数据都评估开启条件并持久化其状态；
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
- **动态数据 schema 归属**：每个关注点下动态数据有哪些字段，由开发者在 `Target` 子类的 `focuses`
  里声明（关注点名 → Pydantic 模型）；`ObservableTarget` 构造时自己从 `type(target).focuses` 取，
  不由外部传入。target 模块的扩展点全部集中在写 `Target` 子类上。
- **上游归属**：可观测目标的上游列表由 `TargetManager` 问 `UpstreamCatalog` 得到，不由外部传入；
  订阅者 acquire 时指定要哪些上游，可观测目标内部按上游路由。
