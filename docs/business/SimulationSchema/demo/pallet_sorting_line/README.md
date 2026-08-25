# 托盘分拣线全链路行为仿真 Demo

> 场景来源：`docs/business/test/1.png`  
> Demo JSON：`full_chain_schema.json`  
> 目标：用现有八段 schema 规范展示“显式连接场景 → Agent 规划 → Runtime 执行 → 动态视图”的完整数据链路。

---

## 1. 场景描述

该 demo 对应图片中的一个简化分拣工位：

```text
托盘 pallet_1 上有 12 个物料；
主传送带 main_conveyor_1 将托盘送到中央分拣位；
robot_1 负责将 part_001 ~ part_006 分拣到上方目标传送带 upper_out_conveyor_1；
robot_2 负责将 part_007 ~ part_012 分拣到下方目标传送带 lower_out_conveyor_1；
两条目标传送带再将分拣后的物料运到出口。
```

当前阶段只处理**显式连接**，不做隐式空间连接推断。因此所有流程边、物理边、信号边都假设已经由用户在前端连接并确认。

---

## 2. 全链路概览

本 demo 的数据传递链路如下：

```text
DeviceSpec
  -> 提供设备接口、信号口、行为能力、runtime_contract

用户显式搭建场景
  -> SceneDocument

Agent / Backend Validator(DeviceSpec + SceneDocument + 用户目标)
  -> SceneValidationReport
  -> 校验通过后继续

Backend Compiler(DeviceSpec + SceneDocument)
  -> SceneTransportSchema

Agent(DeviceSpec + SceneDocument + SceneTransportSchema + 用户目标)
  -> SimPlan

Signal Compiler(DeviceSpec.signal_ports + SceneDocument.signal_edges + SimPlan.signal_rules)
  -> SignalBusSchema

PlanCompiler(DeviceSpec + SceneDocument + SceneTransportSchema + SignalBusSchema + SimPlan)
  -> ExecutableSimGraph / RuntimePlan

Simulation Runtime 启动 run
  -> 初始化 RuntimeSnapshot

仿真运行循环：
  ExecutableSimGraph + 当前 RuntimeSnapshot
    -> DeviceRuntimeProfile

  Scheduler(DeviceRuntimeProfile)
    -> 选择 enabled behavior / 启动 action

  Simulation Runtime(action effects + SignalBus signal_event + 调度结果)
    -> 更新 RuntimeSnapshot

  更新后的 RuntimeSnapshot
    -> 下一轮重新计算 DeviceRuntimeProfile
```

核心边界：

```text
ExecutableSimGraph  是静态可执行规则，定义“能怎么执行”；
RuntimeSnapshot     是运行时原始状态事实，记录“现在执行到哪”；
DeviceRuntimeProfile 是语义化动态视图，表达“现在每台设备能做什么”。
```

---

## 3. 每个结构的职责

### 3.1 DeviceSpec

本 demo 复用已有设备规范：

| 设备规范 | 用到的实例 | 作用 |
|---|---|---|
| `conveyor_1` | `main_conveyor_1`、`upper_out_conveyor_1`、`lower_out_conveyor_1` | 主传送和输出传送。 |
| `robot_arm_1` | `robot_1`、`robot_2` | 分拣机械臂。 |
| `carrier_tray_1` | `pallet_1` | 承载 12 个物料的托盘。 |
| `workpiece_1` | `part_001` ~ `part_012` | 被分拣物料。 |

`DeviceSpec` 不保存场景连接，只定义设备天生能力，例如：

```text
physical_interfaces
process_ports
signal_ports
transport_behaviors
runtime_contract.resources
runtime_contract.fsm_states
```

---

### 3.2 SceneDocument

`SceneDocument` 是场景事实源，由用户显式搭建场景后生成。

它保存：

```text
instances          场景中有哪些设备实例；
materials          托盘和物料初始位置；
process_edges      流程层连接；
physical_edges     物理接口连接；
signal_edges       信号连接；
runtime_config     仿真默认配置。
```

在本 demo 中，关键连接包括：

```text
main_conveyor_1.flow_output -> robot_1.flow_input
main_conveyor_1.flow_output -> robot_2.flow_input
robot_1.flow_output -> upper_out_conveyor_1.flow_input
robot_2.flow_output -> lower_out_conveyor_1.flow_input
```

以及对应的物理接口：

```text
main_conveyor_1.exit -> robot_1.pick_area
main_conveyor_1.exit -> robot_2.pick_area
robot_1.place_area -> upper_out_conveyor_1.entry
robot_2.place_area -> lower_out_conveyor_1.entry
```

---

### 3.3 SceneValidationReport

在生成计划前，Agent / Backend Validator 先校验场景连接是否合理。

本 demo 校验内容包括：

```text
实例是否存在；
设备 spec 是否存在；
process port 方向是否正确；
physical interface 是否兼容；
signal port 方向是否正确；
用户目标是否有可达路径。
```

如果校验失败，链路应暂停，不生成 `SimPlan`。例如：

```text
robot_1.start_pick 不存在；
source signal 不是 output；
main_conveyor_1.exit 无法到达 robot_1.pick_area；
目标传送带容量不足。
```

本 demo 的 `scene_validation_report.status` 为 `passed`，因此继续编译和规划。

---

### 3.4 SceneTransportSchema

`SceneTransportSchema` 由 `DeviceSpec + SceneDocument` 编译生成，不由 Agent 直接生成。

它描述该场景中**理论上可用的物料流转能力**，例如：

```text
main_conveyor_1.entry -> main_conveyor_1.exit
main_conveyor_1.exit -> robot_1.pick_area
main_conveyor_1.exit -> robot_2.pick_area
robot_1.place_area -> upper_out_conveyor_1.entry
robot_2.place_area -> lower_out_conveyor_1.entry
upper_out_conveyor_1.entry -> upper_out_conveyor_1.exit
lower_out_conveyor_1.entry -> lower_out_conveyor_1.exit
```

它不是本次计划，只是 Agent 规划时可用的拓扑上下文。

---

### 3.5 SimPlan

`SimPlan` 由 Agent 生成，输入是：

```text
DeviceSpec
SceneDocument
SceneTransportSchema
用户目标
```

在本 demo 中，Agent 选择如下计划：

```text
1. main_conveyor_1 将 pallet_1 运到分拣位；
2. robot_1 分拣 part_001 ~ part_006 到 upper_out_conveyor_1；
3. robot_2 分拣 part_007 ~ part_012 到 lower_out_conveyor_1；
4. upper_out_conveyor_1 将 A 类物料送到出口；
5. lower_out_conveyor_1 将 B 类物料送到出口。
```

`SimPlan` 仍然是计划层，不直接执行设备。它会被 `PlanCompiler` 编译成 `ExecutableSimGraph`。

---

### 3.6 SignalBusSchema

`SignalBusSchema` 由以下输入联合编译：

```text
DeviceSpec.signal_ports
SceneDocument.signal_edges
SimPlan.signal_rules
```

它定义本次运行实际启用的信号通讯契约：

```text
routes          信号从哪里投递到哪里；
wait_rules      谁等待谁；
payload_schemas 信号 payload 格式；
timeout_rules   超时策略。
```

重要边界：

```text
SignalBusSchema 不保存实时 signal value；
实时信号值保存在 RuntimeSnapshot.signal_values；
每次真实投递由 signal_event 表达；
SignalBusRuntime / SignalDispatcher 负责根据信号规则投递 signal_event。
```

本 demo 的典型路由：

```text
main_conveyor_1.part_ready -> robot_1.start_pick
main_conveyor_1.part_ready -> robot_2.start_pick
robot_1.done -> upper_out_conveyor_1.release_waiting_material
robot_2.done -> lower_out_conveyor_1.release_waiting_material
```

---

### 3.7 ExecutableSimGraph / RuntimePlan

`ExecutableSimGraph` 是 `PlanCompiler` 的产物，输入是：

```text
DeviceSpec
SceneDocument
SceneTransportSchema
SignalBusSchema
SimPlan
```

它定义 Runtime 可执行的静态规则：

```text
action_nodes       有哪些动作；
dependencies       动作之间依赖什么信号；
guards             动作启动前需要满足什么条件；
resource_locks     会占用哪些资源；
effects            on_start / on_complete 如何改变状态；
failure_handlers   异常如何处理；
replan_triggers    何时触发重规划。
```

注意：`ExecutableSimGraph` 虽然是“可执行图”，但它不保存当前状态。它只定义“规则”。

---

### 3.8 RuntimeSnapshot

`RuntimeSnapshot` 由 `Simulation Runtime` 初始化并持续更新。

它是原始状态事实源，保存：

```text
clock
signal_values
device_fsm_states
material_locations
wait_queues
resource_locks
active_actions
```

启动时：

```text
Simulation Runtime(ExecutableSimGraph / RuntimePlan + SceneDocument.materials + DeviceSpec.runtime_contract)
  -> 初始化 RuntimeSnapshot
```

运行中：

```text
Simulation Runtime(action effects + SignalBus signal_event + 调度结果)
  -> 更新 RuntimeSnapshot
```

本 demo 给了两个快照：

```text
runtime_snapshot_initial
  仿真刚启动，托盘在 main_conveyor_1.entry。

runtime_snapshot_after_pallet_arrival
  主传送带已将托盘送到 main_conveyor_1.exit，并发出 part_ready。
```

---

### 3.9 DeviceRuntimeProfile

`DeviceRuntimeProfile` 由：

```text
ExecutableSimGraph + 当前 RuntimeSnapshot
```

实时计算得到。

它是实际传递给 Scheduler、前端和 Agent 的动态视图：

```text
enabled_behaviors   当前可以执行的行为；
waiting_behaviors   当前等待中的行为；
blocked_behaviors   当前阻塞的行为；
executing_behavior  当前正在执行的行为；
next_events         执行后可能产生的事件。
```

在 `runtime_snapshot_after_pallet_arrival` 时刻：

```text
robot_1.pick_and_place enabled；
robot_2.pick_and_place enabled；
upper_out_conveyor_1.transport_to_exit waiting；
lower_out_conveyor_1.transport_to_exit waiting。
```

Scheduler 消费的是 `DeviceRuntimeProfile`，不是直接消费底层 `RuntimeSnapshot`。

---

## 4. 运行时模块分工

运行过程中，各模块职责建议如下：

```text
RunInitializer
  根据 RuntimePlan、SceneDocument.materials 和 DeviceSpec.runtime_contract 初始化 RuntimeSnapshot。

ProfileBuilder
  根据 ExecutableSimGraph + RuntimeSnapshot 计算 DeviceRuntimeProfile。

Scheduler
  读取 DeviceRuntimeProfile.enabled_behaviors，决定启动哪个 action。

ActionExecutor / DeviceBehaviorEngine
  执行动作、推进动作进度、判断动作完成。

SignalBusRuntime / SignalDispatcher
  读取 SignalBusSchema.routes / wait_rules / timeout_rules，投递 signal_event。

EffectApplier / DeviceStateManager
  应用 action effects，修改 FSM、资源锁、物料位置、信号值。

SnapshotManager
  将变更写回 RuntimeSnapshot。
```

---

## 5. 本 demo 的关键事件示例

托盘到达分拣位时，主传送带完成动作：

```text
on_complete:
  move pallet_1 to main_conveyor_1.exit
  emit main_conveyor_1.part_ready
  set main_conveyor_1.fsm_state = waiting_downstream
```

`SignalBusRuntime` 根据 `SignalBusSchema.routes` 投递信号：

```text
main_conveyor_1.part_ready -> robot_1.start_pick
main_conveyor_1.part_ready -> robot_2.start_pick
```

Runtime 更新快照：

```text
RuntimeSnapshot.signal_values.main_conveyor_1.part_ready = true
RuntimeSnapshot.signal_values.robot_1.start_pick = true
RuntimeSnapshot.signal_values.robot_2.start_pick = true
RuntimeSnapshot.material_locations.pallet_1 = main_conveyor_1.exit
```

ProfileBuilder 重新计算：

```text
robot_1.enabled_behaviors includes action_robot_1_sort_a_batch
robot_2.enabled_behaviors includes action_robot_2_sort_b_batch
```

Scheduler 随后启动两个机械臂的分拣动作。

---

## 6. 文件说明

```text
full_chain_schema.json
  一个完整 JSON，将本 demo 的 SceneDocument、SceneValidationReport、SceneTransportSchema、SimPlan、SignalBusSchema、ExecutableSimGraph、RuntimeSnapshot、DeviceRuntimeProfile 和 data_flow_trace 放在同一个文件里，方便阅读全链路。
```

后续如果需要更接近生产结构，可以将该 JSON 拆成：

```text
scene_document.json
scene_validation_report.json
scene_transport_schema.json
sim_plan.json
signal_bus_schema.json
executable_sim_graph.json
runtime_snapshot_initial.json
runtime_snapshot_after_pallet_arrival.json
device_runtime_profiles_after_pallet_arrival.json
```
