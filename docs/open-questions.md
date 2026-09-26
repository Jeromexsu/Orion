# 待决设计问题

审阅过程中发现、尚未拍板的问题。决定后在对应条目写明结论并移到「已决」。

## 待决

### 1. 【重大】子事件模型：obs 应属于子事件，子事件模板是否需要

**发现于**：审阅 target 模块时（2026-09）。**状态**：先理顺 target，之后回来看 event。

**问题**：设计文档里父事件是「目标的命名空间」，不是可观测目标（ObservableTarget）的命名空间；
可观测目标属于子事件，应由子事件 acquire。现在的实现反了：`ParentEvent.add_target()` 由父事件
acquire 可观测目标，然后在 `on_data` 里分发给各模板的槽。

**根源**：实现采用了「模板 → 槽 → 相关数据到来时懒创建实例」的机制。实例在数据到来前不存在，
必须有人先订阅数据，于是只能由父事件订阅。

**模板目前只提供了两样东西**：
1. 同一定义反复触发——实例收敛关闭后，下一条相关数据自动开新实例；
2. 定义不可变、带版本，实例记录按哪个版本运行，便于审计。

**提议的简化模型**（如果子事件是分析师显式创建的监控任务，文档称子事件对应 task）：
- 父事件：目标命名空间（target_id 集合）+ 一组子事件 + `digest()`；自己不订阅任何东西。
- 子事件：显式创建（API 或 hil），创建时带定义（规则 + 算子挂载 + 要观测的 (目标, 关注点, 上游)），
  校验目标在父事件命名空间内后自行 acquire 可观测目标并指定上游；本身就是订阅者；关闭时 release。
- 去掉 `SubEventTemplate`、`SubEventSlot` 和自动开实例；去掉 `ParentEvent.on_data`。
- 顺带解决：不同子事件可订阅不同上游（现在只能按父事件整体订阅）。
- 失去自动重复触发：可由子事件内部推进类算子计数（不关闭），或关闭时由算子提议「再建一个」经 hil 确认。
- 模板的复用价值降级为前端预设表单，不进 core。

**方案 A（保留模板，slot 订阅）**——审阅 event 时理顺：
父事件是静态目标的命名空间，只知道「有哪些目标」，不知道关注点和上游，本来就无法订阅；
真正知道「要观测什么」的是子事件模板，slot 是运行中的模板，由它订阅。slot 在模板装进父事件时
就存在，不必等实例，因此解决了「懒创建实例前没人订阅」的问题。需要改：
1. 模板增加观测声明：每个 (目标, 关注点) 订阅哪些上游（现在条件叶子只有 `t1:position`，没有上游）；
2. 模板校验改为：引用的目标在父事件的静态目标命名空间（target_id 集合）内；
3. slot 在模板装入时按观测声明 acquire，换版本时按新版本重新订阅、多余的 release，移除模板时全部
   release；Dispatcher 直接回调 slot；
4. 父事件变为纯静态：目标命名空间 + slot 集合 + `digest()`，去掉 `on_data` 和 acquire；
   `add_target` 只把 target_id 加入命名空间，移除目标时检查是否仍被模板引用；
5. 重启恢复由 slot 按模板重新订阅，父事件记录不再存上游。

**方案 B（去掉模板）**：即上面的「提议的简化模型」。

**A / B 的分界**：子事件收敛关闭后同样情况再发生，是否需要系统自动开新的？需要选 A，不需要 B 更简单。

**待确认**：
- 子事件关闭后同样情况再发生，是否需要系统自动开新的？（决定选 A 还是 B）
- 子事件创建后定义能否修改？能改是否要版本历史，还是只能「关闭旧的、新建一个」？
- 一个子事件观测多个目标时（如两机接近），acquire 多个可观测目标——理解是否正确？

**影响范围**：event 模块大改（模板 / 槽 / 实例三层合并为 SubEvent），event 仓库接口、重启恢复、
hil 白名单动作、bootstrap、相关测试。

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

### 4. 其他（随审阅推进逐条确认）

- 模板 ID 全局还是按父事件区分（若第 1 条去掉模板则不再适用）。
- 实例关闭条件用 `status["closed"]` 约定，还是显式声明关闭条件（第 1 条定后再看）。
- `EvalResult.outcome`、`Draft.status` 的中文字面值是否对外改为英文枚举。
- 父事件级算子挂载由什么触发。
- 校准钩子的挂载点（设计文档待办）。
- 异步输出算子：`Operator` 加异步标记，依赖队列选型（Celery+Redis vs arq）。
- `SubEventSlot.on_data()` 中途异常导致内存与库不一致（第 1 条重构时一并处理）。
- report 模块是否开 pyright strict。
- 设计文档第八、九节与代码同步。

## 已决

- **契约放哪**：新建 `core/contracts`，跨模块数据契约集中于此（解决 operators「零依赖」自相矛盾）。
- **目标类型写法**：去掉 `TargetType`，每种目标类型继承 `Target` 基类；目标类型只由开发者通过代码定义。
- **动态数据 schema 归属**：每个关注点下动态数据有哪些字段，由开发者在 `Target` 子类的 `focuses`
  里声明（关注点名 → Pydantic 模型）；`ObservableTarget` 构造时自己从 `type(target).focuses` 取，
  不由外部传入。target 模块的扩展点全部集中在写 `Target` 子类上。
- **上游归属**：可观测目标的上游列表由 `TargetManager` 问 `UpstreamCatalog` 得到，不由外部传入；
  订阅者 acquire 时指定要哪些上游，可观测目标内部按上游路由。
