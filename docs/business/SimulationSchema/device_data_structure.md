# 设备与场景行为数据结构定义

> 版本：v0.2
> 日期：2026-08-26
> 阶段：行为建模基线重构
> 背景：删除早期拆得过细的旧中间 schema，收敛为一个核心 Agent 建模结果：`SceneBehaviorGraph`。

---

## 0. 核心结论

当前基线只保留四个一等板块：

| 板块 | 类型 | 归属 | 说明 |
|---|---|---|---|
| `DeviceSpec` | 设备级能力模型 | 设备库 / Postgres | 定义设备原生接口、信号口、行为能力、运行契约和设备特殊约束。 |
| `SceneDocument` | 场景事实模型 | 场景文档 / Postgres | 定义设备实例、位姿、物料、流程边、物理边和信号边。 |
| `SceneBehaviorGraph` | 场景行为模型 | Agent 产物 / 可持久化 | 描述该场景在用户目标下真实如何运行。 |
| `RuntimeSnapshot` | 运行时状态快照 | Runtime memory / Redis，关键 checkpoint 可落库 | 保存当前信号值、设备状态、物料位置、队列、资源锁、负载和 active actions。 |

旧中间产物的职责已经收敛进 `SceneBehaviorGraph`：拓扑能力进入 `modules / behavior_rules`，信号通讯进入 `event_bus`，计划目标与策略进入 `goal / modules / policies`，guards/effects 进入 `behavior_rules / state_transition_rules`。

---

## 1. 分层边界

```text
DeviceSpec 描述“设备天生能做什么”；
SceneDocument 描述“这个场景里有什么、怎么连”；
SceneBehaviorGraph 描述“这个场景在当前目标下实际如何运行”；
RuntimeSnapshot 描述“当前真实运行到什么状态”。
```

### 1.1 DeviceSpec

`DeviceSpec` 不保存场景连接，也不保存运行状态。它只定义设备原生能力，当前行为建模最关心以下字段：

```text
physical_interfaces
process_ports
signal_ports
interface_bindings
transport_behaviors
runtime_contract
type_specific_contract
```

### 1.2 SceneDocument

`SceneDocument` 是场景事实源，保存：

```text
instances
materials
process_edges
physical_edges
signal_edges
runtime_config
```

它可以记录显式信号边，但不负责说明整个场景的动态行为策略。

### 1.3 SceneBehaviorGraph

`SceneBehaviorGraph` 是 Agent 基于 `DeviceSpec + SceneDocument + 用户目标` 生成的场景行为建模结果。

它不是一般约束集合，而是描述该场景真实运作方式的行为图，包括：

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

### 1.4 RuntimeSnapshot

`RuntimeSnapshot` 只保存运行时事实状态，不负责解释行为，也不负责定义行为模型。

```text
RuntimeSnapshot 是当前状态事实；
SceneBehaviorGraph 是行为规则和策略；
Scheduler / Runtime 基于两者决定下一步执行什么。
```

---

## 2. 当前运行链路

```text
1. 设备层建模
   设备库维护 DeviceSpec。

2. 场景搭建
   用户摆放设备、放置物料、显式连接流程边、物理边和信号边。

3. 场景事实保存
   系统保存 SceneDocument。

4. Agent 行为建模
   Agent 读取 DeviceSpec + SceneDocument + 用户目标，生成 SceneBehaviorGraph。

5. Runtime 初始化
   Simulation Runtime 读取 SceneBehaviorGraph 和 SceneDocument.materials，初始化 RuntimeSnapshot。

6. 运行循环
   Scheduler 读取 SceneBehaviorGraph + RuntimeSnapshot，选择可执行行为。
   ActionExecutor 执行动作。
   SignalBusRuntime 按 SceneBehaviorGraph.event_bus 投递事件。
   EffectApplier / SnapshotManager 根据 state_transition_rules 更新 RuntimeSnapshot。
   更新后的 RuntimeSnapshot 进入下一轮循环。
```

---

## 3. SceneBehaviorGraph 推荐结构

```json
{
  "schema_type": "SceneBehaviorGraph",
  "goal": {},
  "modules": [],
  "event_bus": {},
  "state_model": {},
  "behavior_rules": [],
  "state_transition_rules": [],
  "policies": {},
  "completion_conditions": [],
  "failure_observations": []
}
```

### 3.1 `goal`

记录用户目标、场景假设和本次行为建模边界。

### 3.2 `modules`

把场景拆成具有业务意义的运行模块，例如：

```text
托盘运输模块
并行分拣模块
出料传送模块
```

模块可以顺序执行，也可以并行持续运行。

### 3.3 `event_bus`

定义本场景实际使用的事件与信号，而不是只机械复用设备预定义信号。

事件可分为：

```text
设备事件：robot_1.done、upper_out_conveyor_1.blocked
全局事件：global.workpiece_claimed、global.sorting_done
控制事件：robot_1.start_pick、robot_1.pause_pick、robot_1.resume_pick
```

`SignalBusRuntime` 是 Runtime 内部模块，负责按照 `event_bus.routes` 投递事件、广播事件、处理等待唤醒和超时。

### 3.4 `state_model`

定义 RuntimeSnapshot 需要维护的状态变量，例如：

```text
workpiece_pool
material_claims
conveyor_loads
device_states
signal_values
resource_locks
active_actions
```

### 3.5 `behavior_rules`

描述：收到什么事件、满足什么状态条件时，触发哪个设备的哪个行为。

### 3.6 `state_transition_rules`

描述行为开始、完成、失败或事件触发后如何修改状态。

### 3.7 `policies`

描述动态调度策略和函数式判断，例如：

```text
谁空闲谁 claim 下一个物料；
出料传送带 current_load >= max_capacity 时发 blocked；
current_load < resume_threshold 时发 capacity_available；
下游 blocked 时机械臂暂停后续抓取。
```

### 3.8 `completion_conditions`

描述整条流水线完成条件，例如：

```text
工件池为空；
机械臂空闲；
出料传送带清空；
无 active actions。
```

---

## 4. 托盘分拣线建模要点

托盘分拣线不应建模为固定批次：

```text
robot_1 抓 part_001 ~ part_006；
robot_2 抓 part_007 ~ part_012。
```

更合理的基线是：

```text
两个机械臂共享 pallet_1.remaining_parts；
谁空闲谁 claim 一个未处理物料；
出料传送带持续运行；
传送带负载达到阈值后通过 backpressure 暂停对应机械臂；
负载降低后恢复机械臂；
所有物料处理完且传送带清空后结束。
```

这类业务场景下，行为建模结果不只是连接约束，而是场景级事件总线、状态模型和策略函数的组合。

---

## 5. 第一阶段需要定义的设备类型

| 设备类型 | 必需接口 | 必需信号 | 必需行为 |
|---|---|---|---|
| `conveyor` | `entry`、`exit` | `blocked`、`capacity_available`、`done` | `transport_to_exit`、`accept_material` |
| `robot_arm` | `pick_area`、`place_area` | `start_pick`、`pause_pick`、`resume_pick`、`busy`、`done` | `pick_and_place` |
| `workpiece_carrier` | `load_surface`、`carrier_bottom` | `loaded`、`unloaded` | `carry_material`、`release_material` |
| `workpiece` | `grasp_surface`、`bottom` | `picked`、`placed` | 被动对象 |

---

## 6. 后续待细化

- `SceneBehaviorGraph` 转成正式 JSON Schema / Zod。
- Runtime 如何从 `SceneBehaviorGraph` 初始化 `RuntimeSnapshot`。
- `SignalBusRuntime` 的事件投递和 backpressure 策略执行规则。
- Agent 生成 `SceneBehaviorGraph` 的提示词、校验器和可解释报告。
