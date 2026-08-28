# 托盘分拣线 SceneBehaviorGraph Demo

> 场景来源：`docs/business/test/1.png`
> Demo JSON：`full_chain_schema.json`
> 目标：用 v0.2 基线展示 `DeviceSpec + SceneDocument + 用户目标 -> SceneBehaviorGraph -> RuntimeSnapshot` 的完整行为建模链路。

---

## 1. 场景描述

该 demo 对应图片中的简化分拣工位：

```text
托盘 pallet_1 上有多个物料；
主传送带 main_conveyor_1 将托盘送到中央分拣位；
robot_1 和 robot_2 不按固定编号分配物料，而是从共享工件池动态 claim；
两个机械臂持续抓取物料并放到两条出料传送带；
出料传送带持续运行，负载过高时通过 backpressure 暂停机械臂继续抓取；
负载降低后恢复机械臂；
所有物料处理完且传送带清空后，场景结束。
```

当前阶段只处理**显式连接**，不做隐式空间连接推断。

---

## 2. v0.2 全链路

```text
DeviceSpec
  -> 设备原生能力：接口、信号口、行为能力、运行契约。

SceneDocument
  -> 场景事实：设备实例、物料、位姿、显式 process / physical / signal 连接。

Agent(DeviceSpec + SceneDocument + 用户目标)
  -> SceneBehaviorGraph

Runtime(SceneBehaviorGraph + SceneDocument.materials)
  -> 初始化 RuntimeSnapshot

Runtime loop:
  Scheduler 读取 SceneBehaviorGraph + RuntimeSnapshot
  -> 选择可执行行为
  -> ActionExecutor 执行动作
  -> SignalBusRuntime 按 SceneBehaviorGraph.event_bus 投递事件
  -> SnapshotManager 按 SceneBehaviorGraph.state_transition_rules 更新 RuntimeSnapshot
  -> 下一轮循环
```

核心边界：

```text
SceneBehaviorGraph 是持久化行为建模结果，描述“场景应该如何运行”；
RuntimeSnapshot 是高频运行状态事实，描述“当前运行到什么状态”；
SignalBusRuntime 是 Runtime 内部模块，执行 event_bus 路由，不是独立 schema。
```

---

## 3. Demo 文件结构

`full_chain_schema.json` 将以下内容放在同一个文件中，方便阅读：

```text
device_specs
  只保留参与场景事务推理的设备行为字段。

device_spec_usage
  描述设备规范被哪些实例引用。

scene_document
  显式场景事实。

scene_validation_report
  规划前连接校验结果。

scene_behavior_graph
  Agent 生成的场景行为图。

runtime_snapshot_initial
  Runtime 初始化后的状态事实。

```

---

## 4. DeviceSpec 使用方式

本 demo 在 `full_chain_schema.json.device_specs` 中内嵌参与场景事务推理所需的设备行为字段。为了突出场景行为建模，暂不展开 `asset`、`params_schema`、`display_name` 等运行期或展示期才需要的设备参数。

保留字段：

```text
physical_interfaces
process_ports
signal_ports
interface_bindings
transport_behaviors
runtime_contract
type_specific_contract
```

`device_specs` 使用 `device_spec_id` 作为 key：

```text
device_specs.conveyor_1
device_specs.robot_arm_1
device_specs.carrier_tray_1
device_specs.workpiece_1
```

场景实例通过 `SceneDocument.instances[].spec_id` 关联：

```text
main_conveyor_1.spec_id = conveyor_1
robot_1.spec_id = robot_arm_1
pallet_1.spec_id = carrier_tray_1
part_001.spec_id = workpiece_1
```

---

## 5. SceneBehaviorGraph 关键设计

### 5.1 Modules

本场景拆成三个模块：

```text
pallet_transport
  一次性模块：主传送带把托盘送到分拣位。

parallel_robot_sorting
  并行持续模块：两个机械臂从共享工件池 claim 物料并抓取。

output_conveying
  并行持续模块：两条出料传送带持续运输并反馈容量状态。
```

### 5.2 Event Bus

`event_bus` 定义本场景实际启用的事件：

```text
runtime.sim_start
main_conveyor_1.pallet_ready
robot.pick_request
global.workpiece_claimed
robot.pick_done
output_conveyor.blocked
output_conveyor.capacity_available
robot.pause_pick
robot.resume_pick
global.sorting_done
```

这些事件既包含设备事件，也包含全局事件和控制事件。

### 5.3 State Model

`state_model` 定义 RuntimeSnapshot 需要维护的状态：

```text
workpiece_pool
material_claims
conveyor_loads
device_states
signal_values
resource_locks
active_actions
```

其中 `workpiece_pool.pallet_1.remaining_parts` 是共享工件池，解决两个机械臂并行抓取时的物料互斥问题。

### 5.4 Policies

`policies` 描述动态策略：

```text
claim_workpiece
  谁空闲谁从共享工件池原子 claim 一个物料。

target_conveyor_selection
  选择未 blocked 且负载更低的目标传送带。

backpressure
  当出料传送带 current_load >= max_capacity，发 blocked；
  当 current_load <= resume_threshold，发 capacity_available。
```

---

## 6. 典型执行 Trace

```text
1. runtime.sim_start
   -> route to rule:start_pallet_transport
   -> action start main_conveyor_1.transport_to_exit

2. main_conveyor_1.transport_to_exit start
   -> main_conveyor_1 moving，锁住 belt_surface

3. main_conveyor_1.transport_to_exit complete
   -> pallet_1 到达 main_conveyor_1.exit
   -> emit main_conveyor_1.pallet_ready

4. main_conveyor_1.pallet_ready
   -> route to topic:robot_pick_request
   -> Scheduler 唤醒分拣相关 behavior_rules

5. robot_1 / robot_2 idle
   -> emit robot.pick_request

6. claim_workpiece policy
   -> 从 workpiece_pool 原子 claim 一个物料
   -> emit global.workpiece_claimed

7. global.workpiece_claimed
   -> 对应 robot start pick_and_place

8. robot.pick_done
   -> output_conveyor.material_arrived
   -> conveyor_loads.current_load 增加

9. current_load >= max_capacity
   -> emit output_conveyor.blocked
   -> emit robot.pause_pick

10. current_load <= resume_threshold
   -> emit output_conveyor.capacity_available
   -> emit robot.resume_pick

11. completion_conditions 全部满足
   -> emit global.sorting_done
   -> route to runtime:CompletionChecker
```

---

## 7. 和旧 demo 的差异

旧版本把链路拆成：

```text
多个中间 schema 串联（旧拆分链路）
```

v0.2 基线改为：

```text
SceneBehaviorGraph + RuntimeSnapshot
```

原因是托盘分拣这类业务场景更需要描述“场景实际如何持续运行”，包括共享工件池、动态 claim、backpressure 和事件驱动状态变更，而不是拆成多个静态中间约束。
