# SceneBehaviorGraph Agent 技术与学术方案

> 版本：v0.2
> 日期：2026-08-26
> 阶段：基线行为建模方案
> 目标：定义 Agent 如何从自然语言目标、场景事实和设备能力生成最终工艺建模产物 `SceneBehaviorGraph`。

---

## 0. 核心定位

当前基线不再让 Agent 生成多段中间 schema，而是直接生成一个可解释、可校验、可执行的场景行为图：`SceneBehaviorGraph`。

```text
DeviceSpec + SceneDocument + 用户目标
  -> Agent
  -> SceneBehaviorGraph
  -> Runtime 初始化 RuntimeSnapshot
  -> Runtime loop 执行 SceneBehaviorGraph 并持续更新 RuntimeSnapshot
```

其中：

- `DeviceSpec` 描述设备原生能力，即设备“能做什么”。
- `SceneDocument` 描述场景事实，即场景“有什么、怎么显式连接”。
- 用户目标描述本次工艺意图，即“希望这个场景如何运行”。
- `SceneBehaviorGraph` 描述该场景在当前目标下的真实运行机制。
- `RuntimeSnapshot` 只保存高频运行状态事实，不承担行为建模职责。

`SignalBusRuntime` 是 Runtime 内部事件/信号派发模块，不作为独立 schema；它按照 `SceneBehaviorGraph.event_bus` 中定义的事件注册、路由和投递规则执行。

---

## 1. 目标问题

自然语言驱动的行为仿真不是简单把用户描述转换成固定流程图，而是要解决以下问题：

| 问题 | 需要的建模结果 |
|---|---|
| 用户描述的是目标，不一定描述完整工艺流程 | Agent 需要解释目标、补全合理模块、暴露假设。 |
| 同一设备在不同场景下可能启用不同信号和状态 | 设备能力与场景行为必须解耦。 |
| 并行、持续运行、反馈控制场景难以用线性步骤表达 | 需要事件总线、状态模型和策略函数。 |
| 多机器人抢料、传送带超载、资源互斥、死锁等问题跨场景复用 | 需要统一抽象为状态变量 + 策略函数 + 事件反馈。 |
| Agent 生成的行为模型需要可审计、可复现、可执行 | 需要结构化 `SceneBehaviorGraph` 和校验器。 |

因此，Agent 的核心职责不是“编排旧 schema 流水线”，而是生成一个场景级行为模型：

```text
全局事件 + 设备信号 + 信号路由 + 状态变量 + 行为触发 + 状态迁移 + 策略函数 + 完成条件 + 异常观测
```

---

## 2. Agent 节点设计

Agent 建议采用显式节点流水线。节点不一定必须对应独立服务，但应作为可观测的推理阶段记录在 `agent_run` 中。

### 2.1 节点总览

| 节点 | 输入 | 输出 | 作用 |
|---|---|---|---|
| `IntentParserNode` | 用户自然语言目标 | 工艺目标、阶段、约束、指标、用户假设 | 把“想怎么仿真”转成结构化意图。 |
| `SceneUnderstandingNode` | `SceneDocument` | 设备实例、物料、显式连接、可达路径、候选模块 | 理解场景事实，不做隐式连接推断。 |
| `DeviceCapabilityNode` | 相关 `DeviceSpec` | 接口、信号口、行为能力、资源、容量、设备约束 | 建立“可用能力集合”。 |
| `ProcessDecomposerNode` | 意图 + 场景 + 能力 | 业务模块 DAG / 并行区间 / 持续运行模块 | 将目标拆成托盘运输、并行分拣、出料传送等模块。 |
| `EventStateModelerNode` | 模块 + 设备信号 + 场景连接 | `event_bus`、`state_model` 草案 | 设计本场景实际需要的事件、信号、状态变量和 payload。 |
| `BehaviorRuleNode` | 事件状态模型 + 设备行为 | `behavior_rules`、`state_transition_rules` 草案 | 定义事件/条件如何触发行为、行为如何更新状态。 |
| `PolicySynthesizerNode` | 资源问题 + 业务模块 | `policies`、异常观测策略 | 组合共享工件池、backpressure、资源锁、死锁检测等策略。 |
| `ValidationNode` | 行为图草案 + 上游事实 | 校验结果、修复建议 | 校验引用存在性、状态一致性、路由闭环和策略可判定性。 |
| `ExplanationNode` | 校验后的行为图 | 用户可读调度理解说明 | 在提交前展示 Agent 对场景调度的理解。 |

### 2.2 用户确认点

Agent 不应在黑盒中直接写入最终图，而应先展示自己的调度理解：

```text
1. 我识别到的设备和物料是什么；
2. 我把流程拆成哪些模块；
3. 哪些模块顺序运行，哪些模块并行或持续运行；
4. 本场景会注册哪些全局事件和设备信号；
5. Runtime 会维护哪些状态变量；
6. 资源争用、超载、死锁如何处理；
7. 什么条件下判定仿真完成。
```

第一阶段可以采用“解释后默认生成”的交互；如果用于生产或论文实验，建议采用“解释 -> 用户确认 -> 生成”的闭环，便于研究可解释性和用户修正收益。

---

## 3. Agent 工具设计

### 3.1 工具清单

| 工具 | 输入 | 输出 | 说明 |
|---|---|---|---|
| `SceneReader` | `scene_id`、`scene_revision` | `SceneDocument`、实例索引、连接索引 | 读取场景事实和显式连接。 |
| `DeviceSpecReader` | `spec_id`、版本约束 | `DeviceSpec` 能力摘要 | 按场景实例引用读取设备能力。 |
| `GraphValidator` | `SceneBehaviorGraph` 草案 | 校验错误、警告、修复建议 | 校验设备、接口、信号、行为、状态变量引用。 |
| `PolicyLibrary` | 策略名称 + 场景参数 | 策略模板或策略片段 | 提供可复用 shared-pool-claim、capacity-backpressure、resource-lock、deadlock-detection。 |
| `SceneBehaviorGraphWriter` | 校验后的行为图 | 持久化记录 | 写入 `SceneBehaviorGraph`，绑定版本和来源。 |
| `ExplanationRenderer` | 行为图 | 自然语言解释、事件 trace 预览 | 生成用户可读说明和论文演示材料。 |

### 3.2 工具边界

- `SceneReader` 只读场景事实，不替 Agent 推断隐式连接。
- `DeviceSpecReader` 只返回设备原生能力，不直接生成场景行为。
- `PolicyLibrary` 提供策略模板，最终是否启用、参数如何取值由 Agent 根据场景目标决定。
- `GraphValidator` 负责静态可检查问题，不负责替代 Runtime 做连续仿真。
- `SceneBehaviorGraphWriter` 只保存最终行为图，不保存高频运行状态。

---

## 4. 上下文与记忆

### 4.1 短期上下文

基线版本只需要短期上下文：

```text
user_goal
scene_id
scene_revision
device_spec_versions
selected_instances
agent_reasoning_summary
validation_report
```

每次生成 `SceneBehaviorGraph` 必须绑定：

```text
scene_id
scene_revision
device_spec_versions
agent_run_id
```

这样可以避免场景或设备规范变更后继续误用旧行为图。

### 4.2 长期记忆

长期记忆不参与 Runtime 实时决策，只保存可复用建模模式：

```text
分拣线模板
共享工件池模板
出料 backpressure 模板
多机器人资源互斥模板
输送线 deadlock detection 模板
```

长期记忆的作用是提升 Agent 建模稳定性，不应绕过当前 `SceneDocument` 和 `DeviceSpec` 的事实校验。

---

## 5. SceneBehaviorGraph 建模方法

### 5.1 核心格式

`SceneBehaviorGraph` 应至少包含：

| 字段 | 说明 |
|---|---|
| `goal` | 用户目标、场景假设、建模边界。 |
| `modules` | 场景业务模块，支持顺序、并行、持续运行。 |
| `event_bus` | 全局事件、设备信号、控制事件、payload、route、广播/定向规则。 |
| `state_model` | Runtime 需要维护的状态变量。 |
| `behavior_rules` | 事件 + 状态条件 -> 触发设备行为。 |
| `state_transition_rules` | 行为开始、完成、失败、事件触发后如何更新状态。 |
| `policies` | 动态策略函数，如 claim、backpressure、死锁检测、资源锁。 |
| `completion_conditions` | 场景完成条件。 |
| `failure_observations` | 异常观测，如死锁、超载、资源冲突、claim 冲突。 |

### 5.2 五步生成流程

```text
Step 1: 事实索引
  从 SceneDocument 建立 instance_index、material_index、edge_index。

Step 2: 能力索引
  从 DeviceSpec 建立 behavior_index、signal_port_index、resource_index、capacity_index。
  对 conveyor 额外建立 stop_point_model_index，用于判断是否能基于 entry/exit 生成停留点。

Step 3: 模块分解
  将用户目标拆成业务模块，标注顺序、并行、持续运行、前置触发和完成条件。

Step 4: 事件状态建模
  为模块间协作设计事件、信号、状态变量、payload 和路由。
  包含 conveyor 时必须建模 conveyor_stop_points、conveyor_occupancy、conveyor_queues、conveyor_loads。

Step 5: 策略与规则合成
  使用策略模板生成 behavior_rules、state_transition_rules、policies 和 failure_observations。
```

### 5.3 托盘分拣场景映射

| 模块 | 运行方式 | 关键事件 | 关键状态 | 关键策略 |
|---|---|---|---|---|
| `pallet_transport` | 停留点感知顺序模块 | `runtime.sim_start`、`main_conveyor_1.pallet_ready` | `device_states.main_conveyor_1`、`material_locations.pallet_1`、`conveyor_occupancy` | 停留点队列与传送带资源锁。 |
| `parallel_robot_sorting` | 并行持续模块 | `robot.pick_request`、`global.workpiece_claimed`、`robot.pick_done` | `workpiece_pool`、`material_claims`、`device_states.robot_*` | 谁空闲谁 claim。 |
| `output_conveying` | 停留点感知持续模块 | `conveyor.stop_point_occupied`、`conveyor.stop_point_released`、`conveyor.blocked`、`conveyor.capacity_available` | `conveyor_stop_points`、`conveyor_occupancy`、`conveyor_queues`、`conveyor_loads` | queue_wait、capacity_threshold、backpressure。 |

---

## 6. Runtime 与调度方案

### 6.1 Runtime 模块

| 模块 | 说明 |
|---|---|
| `RunInitializer` | 根据 `SceneBehaviorGraph.state_model` 和 `SceneDocument.materials` 初始化 `RuntimeSnapshot`。 |
| `Scheduler` | 读取 `SceneBehaviorGraph + RuntimeSnapshot`，选择当前可执行行为。 |
| `ActionExecutor` | 执行设备行为，如运输、抓取、放置、出料传送。 |
| `SignalBusRuntime` | 按 `event_bus.routes` 派发设备信号、全局事件和控制事件。 |
| `EffectApplier` | 按 `state_transition_rules` 应用状态变化。 |
| `SnapshotManager` | 写回 `RuntimeSnapshot`，维护当前运行事实。 |
| `ObservationEmitter` | 在死锁、超载、资源冲突等情况发出 observation。 |

### 6.2 Runtime loop

```text
while run_status == running:
  Scheduler 读取 SceneBehaviorGraph + RuntimeSnapshot
  Scheduler 找到满足 trigger + guard + policy 的 behavior_rules
  Scheduler 为候选行为申请 resource_locks
  ActionExecutor 启动或推进设备行为
  ActionExecutor 产出 action effects
  SignalBusRuntime 投递 effects 中 emit 的事件
  EffectApplier 应用 state_transition_rules
  SnapshotManager 更新 RuntimeSnapshot
  ObservationEmitter 检查 failure_observations
  CompletionChecker 判断 completion_conditions
```

### 6.3 调度算法建议

第一阶段不需要直接上复杂优化器，建议采用“规则驱动 + 策略函数 + 确定性优先级”的调度算法：

```text
1. 事件触发：筛选当前有新事件或状态变化影响的 rules。
2. Guard 判定：检查状态条件、资源锁、设备状态、容量阈值。
3. Policy 决策：对多个候选执行 claim、目标传送带选择、优先级排序。
4. Conflict resolution：资源互斥冲突时按策略选择一个，其他保留等待。
5. Action dispatch：启动行为并登记 active_actions。
6. Observation check：无可执行行为但任务未完成时触发 deadlock observation。
```

后续如需要学术扩展，可在 `PolicySynthesizerNode` 或 `Scheduler` 中引入约束规划、Petri Net 可达性分析、Temporal Logic 验证或强化学习策略选择，但基线不应被这些复杂方法绑死。

---

## 7. 信号传递与事件总线

### 7.1 注册

所有运行期可能出现的事件必须先在 `SceneBehaviorGraph.event_bus.events` 中注册：

```text
event_id
event_type: device_signal | global_event | control_event | observation
source
payload_schema
default_delivery
retention_policy
```

设备信号需要受 `DeviceSpec.signal_ports` 约束；全局事件和控制事件可以由 Agent 生成，但必须能被 `behavior_rules` 或 `state_transition_rules` 消费。

### 7.2 路由

`event_bus.routes` 定义投递关系：

```text
定向投递：source event -> target device/control rule
广播投递：source event -> subscribers by topic
Runtime 内部投递：source event -> Scheduler / EffectApplier / ObservationEmitter
```

### 7.3 派发

信号值传递由 `SignalBusRuntime` 执行：

```text
ActionExecutor / EffectApplier emit event
  -> SignalBusRuntime 校验事件已注册
  -> 按 routes 投递给目标
  -> 写入 RuntimeSnapshot.signal_values 或事件队列
  -> Scheduler 在下一轮读取事件和状态变化
```

不同业务场景可以有不同信号值、状态值和处理函数，但这些函数必须以结构化策略形式存在于 `policies` 或 `state_transition_rules` 中，并接受静态校验。

---

## 8. 资源调度与异常统一方法

资源问题不应为每个业务硬编码，而应统一抽象为：

```text
状态变量 + 策略函数 + 事件反馈 + 异常观测
```

### 8.1 共享工件池

| 元素 | 建模方式 |
|---|---|
| 状态变量 | `workpiece_pool.pallet_1.remaining_parts`、`material_claims`。 |
| 策略函数 | `claim_workpiece` 原子 claim 一个未处理物料。 |
| 事件反馈 | claim 成功发 `global.workpiece_claimed`，失败发等待或完成检查事件。 |
| 异常观测 | 同一物料被重复 claim 时发 `claim_conflict_detected`。 |

### 8.2 Backpressure

| 元素 | 建模方式 |
|---|---|
| 状态变量 | `conveyor_loads.{conveyor_id}.current_load / max_capacity / resume_threshold / blocked`。 |
| 策略函数 | `capacity_backpressure`。 |
| 事件反馈 | 超阈值或无可用停留点发 `conveyor.blocked`，低于恢复阈值且停留点释放后发 `conveyor.capacity_available`。 |
| 行为影响 | blocked 后暂停对应机械臂后续抓取，available 后恢复。 |

### 8.3 资源互斥

| 元素 | 建模方式 |
|---|---|
| 状态变量 | `resource_locks`、`active_actions`。 |
| 策略函数 | `acquire_lock`、`release_lock`。 |
| 事件反馈 | 锁冲突进入等待队列或发 `resource_conflict_detected`。 |
| 行为影响 | 行为启动前必须获得锁，完成或失败后释放锁。 |

### 8.4 死锁检测

| 元素 | 建模方式 |
|---|---|
| 状态变量 | `active_actions`、`pending_events`、`resource_locks`、`completion_progress`。 |
| 策略函数 | `deadlock_detection`。 |
| 触发条件 | 无可执行行为、仍有未完成任务、存在等待资源或未清空队列。 |
| 异常观测 | 发 `deadlock_detected`，附带等待链、占锁设备和阻塞事件。 |

---

## 9. 数据库与存储

### 9.1 Postgres

Postgres 存结构化事实和可审计结果：

```text
projects
device_specs
scene_documents
scene_behavior_graphs
agent_runs
simulation_runs
simulation_event_logs
```

适合保存版本、权限、索引、审计、查询和关联关系。

### 9.2 JSONB / 对象存储

大体量文档可以使用两种方式：

```text
小中型 JSON：Postgres JSONB 保存全文，便于查询。
大体量 JSON：对象存储保存正文，Postgres 保存 URI、hash、摘要和索引字段。
```

`SceneBehaviorGraph` 建议持久化保存，并绑定：

```text
scene_id
scene_revision
device_spec_versions
agent_run_id
graph_hash
```

### 9.3 Redis

Redis 保存高频运行状态：

```text
RuntimeSnapshot
signal_values
pending_events
resource_locks
active_actions
work queues
simulation frames
```

Redis 不是长期事实库；关键 checkpoint、异常、完成摘要应落 Postgres。

### 9.4 事件流与前端推送

```text
Redis Streams
  Runtime 内部事件流、前端 WebSocket 推送源。

WebSocket
  推送 RuntimeSnapshot 摘要、关键事件和可视化帧。

Postgres event log
  保存低频关键事件，如 overload、deadlock、completion、manual_stop。
```

---

## 10. 场景事务处理

场景事务不是数据库事务的简单映射，而是仿真运行中的一致性边界。

### 10.1 建模事务

Agent 生成 `SceneBehaviorGraph` 时，应将一次建模视为事务：

```text
读取 scene_revision 和 device_spec_versions
生成 graph draft
执行 GraphValidator
生成 explanation
用户确认或系统确认
写入 SceneBehaviorGraph
记录 agent_run
```

写入时要检查场景版本未变化；如果 `scene_revision` 已更新，本次结果应失效并重新生成。

### 10.2 运行事务

Runtime 每轮调度应保证状态更新原子性：

```text
读取 RuntimeSnapshot 版本
选择行为并申请资源锁
执行 action step
投递事件
应用状态迁移
写回新 RuntimeSnapshot 版本
```

如果写回时版本冲突，应重试调度轮次，避免两个行为同时 claim 同一物料或占用同一资源。

---

## 11. 学术创新点

### 11.1 自然语言驱动的场景行为图生成

将传统脚本式工艺建模转化为结构化行为图生成问题：Agent 从用户目标、场景事实和设备能力直接生成 `SceneBehaviorGraph`，而不是依赖人工编写仿真脚本。

### 11.2 设备能力与场景行为解耦

`DeviceSpec` 只定义设备原生能力，`SceneBehaviorGraph` 才定义本场景实际使用的事件、状态、策略和协作关系。这样同一设备可以在不同工艺场景中表现出不同协作行为。

### 11.3 事件总线中心化的工艺建模

用 `event_bus + state_model + behavior_rules` 统一表达设备通信、全局控制、反馈调节和异常观测，比固定流程图更适合并行、持续、反馈控制类工业场景。

### 11.4 策略函数化的资源调度建模

把死锁、超载、共享工件池、资源互斥抽象为可组合策略函数，使 Agent 能复用调度模式并适配不同场景，而不是为每个 demo 写死流程。

### 11.5 可解释 Agent 建模闭环

Agent 在生成最终行为图前展示场景调度理解，使自然语言行为仿真从黑盒生成转变为可解释、可校验、可修正的建模过程。

### 11.6 行为模型与运行状态分离

`SceneBehaviorGraph` 作为持久化行为模型，`RuntimeSnapshot` 作为高频运行状态事实，两者分离后既支持审计复现，也支持实时仿真执行。

### 11.7 约束可校验的生成式仿真建模

Agent 生成结果不是自由文本，而是受设备接口、信号口、行为能力、状态变量和策略模板约束的结构化图，可通过 `GraphValidator` 做静态校验，并通过 Runtime trace 做动态验证。

---

## 12. 验证计划

### 12.1 结构完整性

托盘分拣 demo 的 `scene_behavior_graph` 必须包含：

```text
goal
modules
event_bus
state_model
behavior_rules
state_transition_rules
policies
completion_conditions
failure_observations
```

### 12.2 引用完整性

```text
所有 behavior_rules.then_start_behavior.instance_id 存在于 SceneDocument.instances；
所有 behavior_id 存在于对应 DeviceSpec.transport_behaviors；
所有规则引用的 signal/event 已在 event_bus.events 注册；
所有状态路径已在 state_model 中声明；
所有策略引用的状态变量可被 RuntimeSnapshot 维护。
```

### 12.3 托盘分拣人工 trace

应能手工 trace 以下链路：

```text
runtime.sim_start
  -> main_conveyor_1.pallet_ready
  -> robot.pick_request
  -> global.workpiece_claimed
  -> robot.pick_done
  -> conveyor.blocked
  -> robot.pause_pick
  -> conveyor.capacity_available
  -> robot.resume_pick
  -> global.sorting_done
```

### 12.4 策略正确性

```text
共享工件池 claim 互斥；
backpressure 阈值可触发 blocked 和 capacity_available；
resource_locks 可避免同一设备资源被并发占用；
completion_conditions 可由 RuntimeSnapshot 判定；
deadlock_detection 能在无可执行行为但任务未完成时产生 observation。
```

---

## 13. 当前假设

- 当前不处理用户中途改需求，只做基线行为建模。
- `SceneBehaviorGraph` 是 Agent 的最终工艺建模产物，必须持久化。
- `RuntimeSnapshot` 是运行状态事实，主要在 Runtime memory / Redis 中维护。
- `SignalBusRuntime` 是 Runtime 内部模块，不作为独立 schema。
- 设备状态值、场景状态处理函数和策略函数由 Agent 根据当前业务目标生成，但必须可被静态校验。
