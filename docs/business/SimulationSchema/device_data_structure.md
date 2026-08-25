# 设备数据结构定义

> 版本：v0.1  
> 日期：2026-08-20  
> 阶段：业务逻辑梳理 / 设备结构建模  
> 背景：参考 Visual Components 的组件行为、接口、信号、Process Flow、Transport/Flow 思路，定义本系统自己的设备结构。

---

## 论文视角：行为仿真的建模起点

本文档中的所有 schema 组合起来，可以理解为一个面向三维工业场景的 **工艺行为建模体系**。它不是为了单纯保存前端场景，而是为了让 Agent 和 Simulation Runtime 能够理解：场景中有哪些设备、物料按什么工艺流转、设备之间如何连接和通讯、某个运行状态下设备可以执行哪些行为。

因此，基于 Agent 的行为仿真可以先拆成两个建模问题：

| 建模问题       | 关注对象                                                                   | 产物                                                                                                            |
| -------------- | -------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| 工艺层行为建模 | 整个工艺场景如何运行，物料如何流转，设备之间如何协作，信号和状态如何传播。 | `SceneDocument`、`SceneTransportSchema`、`SignalBusSchema`、`SimPlan`、`ExecutableSimGraph`                     |
| 设备层行为建模 | 单台设备为了参与上述工艺仿真，必须暴露哪些标准化能力和运行契约。           | `DeviceSpec`、`physical_interfaces`、`process_ports`、`signal_ports`、`transport_behaviors`、`runtime_contract` |

研究路径上，建议先从工艺层出发，整理一个工艺场景运行时需要表达的状态和关系：

```text
物料在哪里；
设备之间如何流转；
谁需要等待谁；
哪些信号会触发动作；
哪些资源会被占用；
运行异常如何暴露给 Agent。
```

然后再根据这些行为仿真需求，反向规范设备层数据结构。也就是说，`DeviceSpec` 的字段不是为了“描述一个模型文件”而存在，而是为了支撑工艺层行为仿真：设备必须能被连接、被调度、接收信号、发出状态、执行 transport 行为，并在运行时形成可计算的 `DeviceRuntimeProfile`。

这里的“接口层”不应只理解为物理接口。更准确地说，设备层行为建模是以 `Interface / Connector` 为锚点，把流程口、信号口、Transport / Flow 行为能力和运行契约组织成标准化的设备行为接口模型。

这形成了两条互补的 schema 推理路径：

| 推理路径                   | 出发点                     | 推理方向                                             | 产物                                                                             | 作用                                              |
| -------------------------- | -------------------------- | ---------------------------------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------- |
| 自顶向下的 schema 规范推理 | 场景级工艺仿真运行需要什么 | 从八大 schema 板块反推设备层 `DeviceSpec` 应如何规范 | 设备建模规范、接口规范、行为契约规范                                             | 服务论文方法论和系统 schema 设计。                |
| 自底向上的实际 schema 推理 | 当前场景实际选用了哪些设备 | 从具体 `DeviceSpec` 编译生成场景级运行 schema        | `SceneDocument`、`SceneTransportSchema`、`SignalBusSchema`、`ExecutableSimGraph` | 服务真实场景搭建、Agent 计划生成和 Runtime 执行。 |

换句话说：

```text
研究设计阶段：
  先问“工艺仿真需要哪些 schema”，再推导“设备 schema 必须怎么定义”。

系统运行阶段：
  先加载“场景中用到的设备 schema”，再生成“这个场景的运行 schema”。
```

前者保证设备建模规范不是拍脑袋设计，而是由工艺仿真需求反推出来；后者保证实际系统可以从具体设备实例出发，自动生成场景运行所需的拓扑、信号和调度结构。

---

## 0. 总览：分层与运行链路

本文档后续所有字段定义都围绕一个原则展开：**设备能力、场景事实、计划目标、运行状态必须分层表达，不能混成一个大对象。**

当前建议拆成八个核心板块：

| 板块                                 | 类型              | 归属                                        | 说明                                                                                                                     |
| ------------------------------------ | ----------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `DeviceSpec`                         | 设备级 schema     | Postgres / 设备库                           | 定义设备天生具备的参数、物理连接接口、流程口、信号口和 Transport / Flow 行为能力。                                       |
| `SceneDocument`                      | 场景级事实 schema | Postgres / 场景文档                         | 定义场景中有哪些设备实例，以及设备实例之间的 process、physical、signal 关系。                                            |
| `SceneTransportSchema`               | 场景级派生 schema | 可缓存 / 可重建                             | 根据 `DeviceSpec + SceneDocument` 中的显式连接编译出当前场景中可用的物料流转和 transport 行为拓扑。                      |
| `SignalBusSchema`                    | 信号级派生 schema | 可缓存 / 可重建                             | 根据设备信号口、场景信号边和 `SimPlan.signal_rules` 编译出本次运行实际启用的信号路由、等待规则、payload 约束和超时策略。 |
| `SimPlan`                            | Agent 计划产物    | Postgres / Agent run                        | Agent 根据用户目标、场景和设备能力生成的本次仿真计划。                                                                   |
| `ExecutableSimGraph` / `RuntimePlan` | 可执行计划        | Simulation Runtime 派生                     | Runtime 将 `SimPlan` 编译成可执行描述，包括步骤前置条件、等待条件、资源锁、输入信号、输出信号、完成效果和失败策略。      |
| `RuntimeSnapshot`                    | 运行时状态        | Redis / Runtime memory，关键事件落 Postgres | 保存当前 signal value、设备 FSM、物料位置、等待队列、资源锁、active action 和仿真时钟。                                  |
| `DeviceRuntimeProfile`               | 当前设备行为画像  | Runtime 派生 / 可推送前端                   | 根据 `ExecutableSimGraph + RuntimeSnapshot` 实时计算某个设备实例当前可执行、等待、阻塞或正在执行哪些行为。               |

最重要的边界是：

```text
DeviceSpec 描述“设备天生能做什么”；
SceneDocument 描述“这个场景里有什么、怎么连”；
SceneTransportSchema 描述“这个场景理论上能怎么流转”；
SimPlan 描述“这次仿真计划要做什么”；
SignalBusSchema 描述“这次计划实际启用哪些信号通讯规则”；
ExecutableSimGraph 描述“这次计划如何被 Runtime 执行”；
RuntimeSnapshot 描述“当前真实运行到什么状态”；
DeviceRuntimeProfile 描述“这个设备此刻真的能做什么”。
```

其中 `RuntimeSnapshot` 和 `DeviceRuntimeProfile` 的边界需要特别区分：

```text
RuntimeSnapshot 是运行时状态事实 / 原始快照 / checkpoint，负责记录“现在真实状态是什么”；
DeviceRuntimeProfile 是基于 RuntimeSnapshot 计算出的语义化行为视图，负责把状态解释成 Scheduler、前端和 Agent 可消费的信息。
```

也就是说，`RuntimeSnapshot` 不负责解释，`DeviceRuntimeProfile` 才是实际向调度器、前端展示和 Agent observation 传递的行为信息层。但 `DeviceRuntimeProfile` 不替代 `RuntimeSnapshot`：恢复、回放、精确状态计算和资源锁判断仍以 `RuntimeSnapshot` 为底层事实源。

完整运行链路如下：

```text
用户搭建显式连接场景 + 描述仿真目标
  -> SceneDocument + 用户目标

Agent / Backend Validator(DeviceSpec + SceneDocument + 用户目标)
  -> SceneValidationReport
  -> 若不合理：返回原因、影响和修复建议，暂停规划
  -> 若合理：继续生成后续运行结构

DeviceSpec + SceneDocument
  -> SceneTransportSchema

Agent(DeviceSpec + SceneDocument + SceneTransportSchema + 用户目标 + 可选 RuntimeSnapshot)（这里的“可选 RuntimeSnapshot”意思是：不是每次生成 SimPlan 都需要运行时快照，只有在仿真已经开始或中途修改需求时才需要。）
  -> SimPlan

DeviceSpec.signal_ports + SceneDocument.signal_edges + SimPlan.signal_rules
  -> SignalBusSchema

PlanCompiler(DeviceSpec + SceneDocument + SceneTransportSchema + SignalBusSchema + SimPlan)
  -> ExecutableSimGraph / RuntimePlan

Simulation Runtime(ExecutableSimGraph / RuntimePlan + SceneDocument.materials + DeviceSpec.runtime_contract)
  -> 初始化 RuntimeSnapshot

仿真运行循环：
ExecutableSimGraph + 当前 RuntimeSnapshot
  -> DeviceRuntimeProfile

Scheduler(DeviceRuntimeProfile)
  -> 选择 enabled behavior / 启动 action / 占用资源锁

Simulation Runtime(action effects + SignalBus signal_event + 调度结果)
  -> 更新 RuntimeSnapshot

更新后的 RuntimeSnapshot
RuntimeSnapshot + DeviceRuntimeProfile
  -> Redis 缓存 / WebSocket 推送 / 关键事件落 Postgres

用户中途追加要求或 Runtime 产生异常 observation
  -> Agent(DeviceSpec + SceneDocument + SceneTransportSchema + 当前 RuntimeSnapshot + 用户新目标)
  -> 生成修订后的 SimPlan / RemainingSimPlan
```

因此，`DeviceRuntimeProfile` 不是场景事实源，也不是长期保存的设备 schema。它是运行时动态视图，会随着 `RuntimeSnapshot` 的变化持续更新。真正的场景级可执行能力描述应命名为 `SceneTransportSchema`。

---

## 1. 核心判断：从四层概念升级为两级建模

原来的 `Interface / Connector`、`Signal`、`Process Flow`、`Transport / Flow` 四层仍然成立，但它们不再作为最终章节框架，而是升级为工艺行为仿真的基础建模语言。

新的论文与系统口径应拆成两级：

```text
工艺层行为建模
  描述整个工艺场景需要哪些设备、连接、流转路径、信号依赖、计划、运行状态和调度视图。

设备层行为建模
  描述不同类型设备如何以统一接口暴露自身能力，同时保留机械臂、传送带、仓储等设备的运动和控制特殊性。
```

这两级建模存在方向相反但互相闭环的推理路径：研究上先自顶向下定义工艺仿真需要的八大 schema，再反推设备 schema 规范；系统运行时则从具体设备 schema 自底向上编译出场景级运行 schema。

四层概念在新框架中的位置如下：

| 原四层概念              | 在新框架中的位置                                               | 主要 schema                                                                                                        |
| ----------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `Interface / Connector` | 设备层定义连接能力，场景层定义连接事实。                       | `DeviceSpec.physical_interfaces`、`DeviceSpec.process_ports`、`interface_bindings`、`SceneDocument.physical_edges` |
| `Signal`                | 设备层定义信号口，场景层定义信号关系，运行层维护实时信号状态。 | `DeviceSpec.signal_ports`、`SceneDocument.signal_edges`、`SignalBusSchema`、`RuntimeSnapshot.signal_values`        |
| `Process Flow`          | 工艺层定义物料或产品的业务流转路径。                           | `SceneDocument.process_edges`、`SimPlan.process_route`                                                             |
| `Transport / Flow`      | 设备层定义可执行行为能力，工艺层编译出可执行的物料流转拓扑。   | `DeviceSpec.transport_behaviors`、`SceneTransportSchema`、`ExecutableSimGraph`、`DeviceRuntimeProfile`             |

因此，当前的“大 schema”不是单个 JSON，而是一组互相编译、互相约束的 schema 集合。它们共同回答工艺行为仿真的核心问题：

```text
场景里有什么设备；
设备之间怎么连；
物料按什么工艺流转；
信号如何触发和等待；
Agent 计划要执行什么；
Runtime 当前运行到什么状态；
每台设备此刻可以做什么。
```

---

## 2. 工艺层行为建模：八个核心 schema 板块

工艺层行为建模不是只保存流程图，而是要覆盖整个行为仿真所需的全部信息。第一阶段建议固定为八个核心板块。

### 2.1 `DeviceSpec`：设备能力输入

`DeviceSpec` 属于设备层建模产物，但它是工艺层编译的第一输入。它定义设备天生具备什么能力，而不定义某个具体场景中它要和谁连接。

```json
{
  "spec_id": "spec_robot_v1",
  "device_type": "robot",
  "version": "1.0.0",
  "asset": { "model_format": "glb", "model_key": "models/robot.glb" },
  "params_schema": {},
  "physical_interfaces": [],
  "process_ports": [],
  "signal_ports": [],
  "interface_bindings": [],
  "transport_behaviors": [],
  "runtime_contract": {}
}
```

它回答：单台设备有哪些参数、物理连接接口、流程接口、信号接口、行为能力和运行契约。

### 2.2 `SceneDocument`：场景事实 schema

`SceneDocument` 是场景事实源，记录当前场景里选用了哪些设备实例，以及这些实例之间的工艺、物理和信号关系。

```json
{
  "scene_id": "scene_01",
  "revision": 12,
  "instances": [],
  "process_edges": [],
  "physical_edges": [],
  "signal_edges": [],
  "materials": [],
  "runtime_config": {}
}
```

它回答：场景里有什么、设备实例怎么摆放、流程怎么连、物理接口怎么连、信号关系怎么连。

### 2.3 `SceneTransportSchema`：场景物料流转 schema

`SceneTransportSchema` 是由 `DeviceSpec + SceneDocument` 编译出来的场景级派生 schema。它不是人工维护的第一事实，而是可缓存、可重建的工艺流转拓扑。

```json
{
  "schema_id": "transport_schema_scene_01_r12",
  "scene_id": "scene_01",
  "scene_revision": 12,
  "transport_nodes": [],
  "transport_edges": [],
  "behavior_bindings": [],
  "diagnostics": []
}
```

它回答：在当前场景结构下，哪些设备之间理论上可以发生物料流转，哪些 `transport_behaviors` 被场景连接关系激活。

### 2.4 `SignalBusSchema`：信号通讯 schema

`SignalBusSchema` 是根据 `DeviceSpec.signal_ports + SceneDocument.signal_edges + SimPlan.signal_rules` 编译出来的信号运行契约。

```json
{
  "schema_id": "signal_schema_run_001",
  "routes": [],
  "wait_rules": [],
  "payload_schemas": {},
  "timeout_rules": []
}
```

它回答：哪些信号可以路由到哪些设备，哪些状态会造成等待，等待如何释放，超时后如何上报 Runtime 或 Agent。

### 2.5 `SimPlan`：Agent 生成的仿真计划

`SimPlan` 是 Agent 根据用户目标、场景结构、设备能力和可选运行时状态生成的本次仿真计划。

```json
{
  "sim_plan_id": "plan_001",
  "goal": "move boxes from conveyor_1 to conveyor_2 using robot_1",
  "process_route": [],
  "selected_devices": [],
  "transport_steps": [],
  "signal_rules": [],
  "success_criteria": [],
  "interrupt_policy": {}
}
```

它回答：这次仿真要达成什么目标、采用哪条工艺路线、选择哪些设备行为、成功条件和打断策略是什么。

### 2.6 `ExecutableSimGraph` / `RuntimePlan`：可执行计划 schema

`ExecutableSimGraph` 是 Runtime 把 `SimPlan` 编译成可执行图后的结果。它比 `SimPlan` 更低层，直接服务调度器。

```json
{
  "runtime_plan_id": "runtime_plan_001",
  "nodes": [],
  "edges": [],
  "guards": [],
  "actions": [],
  "effects": [],
  "resource_requirements": [],
  "replan_triggers": []
}
```

它回答：每一步启动前要满足什么条件，执行时占用哪些资源，完成后改变哪些状态，异常时是否触发重规划。

### 2.7 `RuntimeSnapshot`：运行时状态 schema

`RuntimeSnapshot` 保存当前仿真状态，主要位于 Redis / Runtime memory，关键事件摘要落 Postgres。它不是长期场景事实。

`RuntimeSnapshot` 由 Simulation Runtime 在执行 `ExecutableSimGraph / RuntimePlan` 的过程中初始化并持续更新。它不是 Agent 生成的，也不是用户手写的，而是 Runtime 根据可执行图、信号投递、调度结果、动作 effects、资源锁和物料位置变化维护出来的全局运行状态。

首次启动仿真时，Runtime 会生成初始快照：

```text
run_id              来自本次 simulation run；
clock               初始化为 0；
device_fsm_states   来自各设备 DeviceSpec.runtime_contract.default_state；
signal_values       来自默认信号值或初始化为空；
material_locations  来自 SceneDocument.materials 的初始 located_at；
wait_queues         根据设备 capacity / queue 规则初始化为空队列；
resource_locks      根据 ExecutableSimGraph.resource_locks 初始化为未占用；
active_actions      初始化为空。
```

运行过程中，每个 action 的 `on_start`、`on_complete`、`on_error` 等 effects 会持续更新 `RuntimeSnapshot`。例如动作开始时可以设置 `busy` 信号、加资源锁、写入 active action；动作完成时可以发出 `done` 信号、移动物料位置、释放资源锁并清理 active action。

```json
{
  "run_id": "run_001",
  "clock": 12.5,
  "signal_values": {},
  "device_fsm_states": {},
  "material_locations": {},
  "wait_queues": {},
  "resource_locks": {},
  "active_actions": {}
}
```

它回答：当前信号值是什么、设备处于什么状态、物料在哪里、谁在等待、哪些资源被占用、哪些动作正在执行。

生成关系可以概括为：

```text
SceneDocument.materials
DeviceSpec.runtime_contract.default_state
ExecutableSimGraph.guards / effects / resource_locks
SignalBusSchema.routes / wait_rules / timeout_rules
Scheduler 执行动作结果
  -> Simulation Runtime 初始化并持续更新
  -> RuntimeSnapshot
```

### 2.8 `DeviceRuntimeProfile`：设备当前行为画像

`DeviceRuntimeProfile` 是由 `ExecutableSimGraph + RuntimeSnapshot` 实时计算出来的设备级动态视图。它不是设备源数据，也不是场景事实。

它的定位是运行时状态解释层：`RuntimeSnapshot` 只保存 signal value、FSM、物料位置、等待队列、资源锁和 active actions 等原始状态；`DeviceRuntimeProfile` 则把这些原始状态结合 `ExecutableSimGraph` 的 guards、dependencies、effects 和 resource requirements，计算成某台设备当前的 `enabled`、`waiting`、`blocked`、`executing` 行为集合。

因此，实际传递给 Scheduler、前端和 Agent 的通常应是 `DeviceRuntimeProfile`，而不是直接把底层 `RuntimeSnapshot` 暴露给它们：

```text
RuntimeSnapshot
  -> 状态事实源 / checkpoint / 恢复与回放依据

DeviceRuntimeProfile
  -> Scheduler 选择 enabled behavior
  -> 前端展示执行、等待、阻塞原因
  -> Agent 作为 observation 解释状态或重规划
```

```json
{
  "device_instance_id": "robot_1",
  "current_state": "idle",
  "enabled_behaviors": [],
  "waiting_behaviors": [],
  "blocked_behaviors": [],
  "executing_behavior": null,
  "next_events": []
}
```

它回答：某台设备此刻能执行什么、正在等待什么、被什么条件阻塞、执行完成后会产生哪些信号或状态变化。

---

## 3. 设备层行为建模：通用接口与设备特殊性

设备层行为建模的任务，是让机械臂、传送带、仓储、工件等不同设备都能被同一个工艺层 schema 编排，同时不抹平它们的运动差异。

### 3.1 通用层：所有设备都应暴露的行为接口

无论设备类型如何，第一阶段都应尽量收敛到统一的设备行为接口模型：

| 通用字段              | 作用                                                              |
| --------------------- | ----------------------------------------------------------------- |
| `params_schema`       | 定义速度、容量、负载、节拍等可配置参数。                          |
| `physical_interfaces` | 定义真实连接锚点，例如入口、出口、抓取区、放置区。                |
| `process_ports`       | 定义工艺流程口，例如 `flow_input`、`flow_output`。                |
| `signal_ports`        | 定义可接收或发出的运行时信号，例如 `busy`、`done`、`part_ready`。 |
| `interface_bindings`  | 定义流程口如何绑定到真实物理接口。                                |
| `transport_behaviors` | 定义设备可执行的物料流转行为能力。                                |
| `runtime_contract`    | 定义 FSM 状态、资源、容量、错误状态和运行时约束。                 |

场景层只依赖这些通用字段做编排：它不需要提前知道机械臂和传送带内部运动算法完全不同，只需要知道它们有哪些接口、信号和行为能力。

### 3.2 特殊层：不同设备保留自己的运动与控制特性

通用接口解决“能被编排”，特殊字段解决“如何真实仿真”。二者不能混。

| 设备类型    | 通用接口表现                                                                                                | 设备特殊性                                              |
| ----------- | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| `conveyor`  | 有 `entry`、`exit`、`flow_input`、`flow_output`、`part_ready`、`blocked`、`transport_to_exit`。             | 连续输送、速度、长度、容量、阻塞传播、物料队列。        |
| `robot`     | 有 `pick_area`、`place_area`、`flow_input`、`flow_output`、`start_pick`、`busy`、`done`、`pick_and_place`。 | 离散抓取、关节运动、TCP、工作空间、夹爪资源、路径规划。 |
| `storage`   | 有 `cell_input`、`cell_output`、`cell_available`、`stored`、`store_to_cell`。                               | 库位分配、容量、预约、入库/出库策略。                   |
| `workpiece` | 有物料类型、尺寸、可抓取面、可放置面。                                                                      | 通常是被动对象，不主动执行 transport 行为。             |

因此设备建模规范应采用“通用 envelope + type-specific behavior”的形式：

```json
{
  "device_type": "robot",
  "common_contract": {
    "physical_interfaces": [],
    "process_ports": [],
    "signal_ports": [],
    "transport_behaviors": []
  },
  "type_specific_contract": {
    "kinematics": {},
    "workspace": {},
    "gripper": {},
    "motion_profile": {}
  }
}
```

传送带和机械臂的运动特性不一致，但它们都必须通过同一组通用接口进入场景编排。这样 `SceneDocument`、`SceneTransportSchema`、`SignalBusSchema` 才能以统一方式组织整体工艺仿真。

---

## 4. 工艺仿真编译链路

完整编译链路可以理解为从“设备能力”和“显式场景事实”出发，先校验连接合理性，再生成计划、信号规则和可执行图，最后进入运行时调度。当前阶段只处理用户显式连接，隐式连接推断作为后续能力补充。

```text
1. 设备层建模
   定义不同设备类型的 DeviceSpec，包括通用接口和特殊行为能力。

2. 场景搭建
   用户在三维场景和流程画布中选择设备、摆放设备、显式连接流程口、确认物理关系和信号关系。

3. 场景事实保存
   系统保存 SceneDocument，包括 instances、process_edges、physical_edges、signal_edges。

4. 场景连接校验
   Agent / Backend Validator 根据 DeviceSpec + SceneDocument + 用户目标校验连接是否合理。
   如果不合理，返回引用错误、方向错误、类型不兼容、不可达路径、缺失信号或资源冲突等原因，并给出修复建议。
   如果合理，继续后续编译和规划。

5. 场景行为编译
   Backend 根据 DeviceSpec + SceneDocument 编译 SceneTransportSchema，得到本场景可用的 transport nodes、transport edges 和 behavior bindings。

6. Agent 生成计划
   Agent 根据 DeviceSpec、SceneDocument、SceneTransportSchema 和用户目标生成 SimPlan。

7. 信号规则编译
   Backend / Runtime 根据 DeviceSpec.signal_ports、SceneDocument.signal_edges 和 SimPlan.signal_rules 编译 SignalBusSchema。
   SceneDocument.signal_edges 表示场景中已有的显式信号连接；SimPlan.signal_rules 表示本次计划实际使用的信号规则；SignalBusSchema.routes 表示运行时实际启用的信号路由。

8. 可执行图编译
   PlanCompiler / Runtime 将 DeviceSpec、SceneDocument、SceneTransportSchema、SignalBusSchema 和 SimPlan 编译为 ExecutableSimGraph / RuntimePlan。

9. 实时调度执行
   Scheduler 根据 RuntimeSnapshot 计算 DeviceRuntimeProfile，并执行 enabled behavior。

10. 运行时状态更新
    Simulation Runtime 根据 action effects、SignalBus 投递结果、物料位置变化、设备 FSM 变化、等待队列和资源锁变化持续更新 RuntimeSnapshot。

11. 状态推送与观测
    RuntimeSnapshot 和 DeviceRuntimeProfile 可缓存到 Redis，并通过 WebSocket 推送给前端；关键低频事件可写入 Postgres 事件表，供审计、回放、异常诊断和 Agent 重规划使用。
```

这个链路的关键点是：

```text
Agent 先校验场景连接，再生成 SimPlan；
Agent 不直接驱动设备；
SimPlan 先于本次运行的 SignalBusSchema 完成；
SceneDocument.signal_edges 是场景事实，SimPlan.signal_rules 是本次计划选择；
SignalBusSchema.routes 是 Runtime 实际启用的信号路由；
PlanCompiler / Runtime 编译可执行图；
Scheduler 消费 DeviceRuntimeProfile；
SignalBus 投递 signal_event；
RuntimeSnapshot 由 Simulation Runtime 初始化并持续更新；
RuntimeSnapshot 是运行状态快照，不是 Agent 计划产物，也不是 SceneDocument 场景事实。
```

---

## 5. 推荐 DeviceSpec 完整结构

```json
{
  "spec_id": "spec_robot_v1",
  "device_type": "robot",
  "display_name": "Robot Arm",
  "version": "1.0.0",

  "asset": {
    "model_format": "glb",
    "model_key": "models/robot/robot_arm.glb"
  },

  "params_schema": {
    "speed_mps": { "type": "number", "min": 0.05, "max": 2.0, "default": 0.5 },
    "payload_kg": { "type": "number", "min": 0.0, "max": 20.0, "default": 5.0 }
  },

  "physical_interfaces": [
    {
      "interface_id": "pick_area",
      "kind": "material",
      "direction": "input",
      "node_name": "PickAnchor",
      "material_classes": ["box"]
    },
    {
      "interface_id": "place_area",
      "kind": "material",
      "direction": "output",
      "node_name": "PlaceAnchor",
      "material_classes": ["box"]
    }
  ],

  "process_ports": [
    { "port_id": "flow_input", "direction": "input", "label": "Input" },
    { "port_id": "flow_output", "direction": "output", "label": "Output" }
  ],

  "signal_ports": [
    { "port_id": "start_pick", "direction": "input", "value_type": "event" },
    { "port_id": "busy", "direction": "output", "value_type": "boolean" },
    { "port_id": "done", "direction": "output", "value_type": "event" },
    { "port_id": "error", "direction": "output", "value_type": "event" }
  ],

  "interface_bindings": [
    { "process_port": "flow_input", "physical_interface": "pick_area" },
    { "process_port": "flow_output", "physical_interface": "place_area" }
  ],

  "transport_behaviors": [
    {
      "behavior_id": "pick_and_place",
      "behavior_type": "material_transfer",
      "input_physical_interface": "pick_area",
      "output_physical_interface": "place_area",
      "default_algorithm": "robot_pick_place",
      "input_signals": ["start_pick"],
      "output_signals": ["busy", "done", "error"],
      "resources": ["robot_arm", "gripper"],
      "fsm_states": ["idle", "busy", "error"],
      "default_state": "idle"
    }
  ],

  "runtime_contract": {
    "fsm_states": ["idle", "busy", "waiting", "error"],
    "default_state": "idle",
    "resources": [
      { "resource_id": "robot_arm", "exclusive": true },
      { "resource_id": "gripper", "exclusive": true }
    ],
    "capacity": { "max_active_materials": 1 },
    "error_policy": {
      "on_timeout": "emit_observation",
      "on_unreachable_target": "pause_and_request_replan"
    }
  },

  "type_specific_contract": {
    "kinematics": { "model": "abstract_robot_arm" },
    "workspace": { "shape": "sphere", "radius_m": 1.2 },
    "gripper": { "supported_material_classes": ["box"], "max_payload_kg": 5.0 },
    "motion_profile": {
      "default_move_type": "pick_place",
      "collision_check": false
    }
  }
}
```

---

## 6. 推荐 SceneDocument 设备相关结构

```json
{
  "scene_id": "scene_01",
  "revision": 1,
  "instances": [
    {
      "instance_id": "robot_1",
      "spec_id": "spec_robot_v1",
      "device_type": "robot",
      "name": "Robot 1",
      "transform": {
        "position": [0.0, 0.0, 0.0],
        "rotation_euler": [0.0, 0.0, 0.0],
        "scale": [1.0, 1.0, 1.0]
      },
      "params": {
        "speed_mps": 0.5,
        "payload_kg": 5.0
      },
      "visible": true,
      "locked": false
    }
  ],
  "process_edges": [],
  "physical_edges": [],
  "signal_edges": [],
  "runtime_config": {
    "deadlock_detection": true,
    "default_signal_timeout_s": 30
  }
}
```

---

## 7. 业务规则

### 7.1 命名规则

- `physical_interfaces` 用真实语义命名：`entry`、`exit`、`pick_area`、`place_area`。
- `process_ports` 第一阶段统一为：`flow_input`、`flow_output`。
- `signal_ports` 用事件/状态语义命名：`busy`、`done`、`part_ready`、`start_pick`。
- `transport_behaviors` 用动作能力命名：`transport_to_exit`、`pick_and_place`、`store_to_cell`。

### 7.2 层级边界

- `DeviceSpec` 不保存场景连接关系，只定义设备能力。
- `SceneDocument` 不保存当前运行状态，只保存场景事实。
- `SceneTransportSchema` 和 `SignalBusSchema` 是派生 schema，必须能从事实源重新编译。
- `SimPlan` 不直接驱动设备，只表达 Agent 计划目标和行为选择。
- `ExecutableSimGraph` / `RuntimePlan` 面向调度器，不面向用户直接编辑。
- `RuntimeSnapshot` 不作为长期事实库，Redis 状态必须能被事件日志或 checkpoint 解释。
- `DeviceRuntimeProfile` 是动态视图，不是设备源数据，也不是场景源数据。

### 7.3 运行时状态边界

以下状态不写入设备规范，也不写入 SceneDocument：

- 当前 `busy` 值。
- 当前物料等待队列。
- 当前资源锁。
- 当前 FSM 状态。
- 当前仿真帧位置。

这些状态属于 Simulation Runtime / Redis。

---

## 8. 第一阶段需要定义的设备类型

建议先定义最少四类：

| 设备类型    | 必需接口                              | 必需信号                                | 必需行为             |
| ----------- | ------------------------------------- | --------------------------------------- | -------------------- |
| `conveyor`  | `entry`、`exit`                       | `part_ready`、`blocked`、`done`         | `transport_to_exit`  |
| `robot`     | `pick_area`、`place_area`             | `start_pick`、`busy`、`done`、`error`   | `pick_and_place`     |
| `workpiece` | `bottom`、`top` 可选                  | 无或 `picked`、`placed`                 | 被动对象，不主动执行 |
| `storage`   | `cell_input` 或 cell-level interfaces | `cell_available`、`cell_full`、`stored` | `store_to_cell`      |

当前可以先从 `conveyor + robot + workpiece` 开始，因为你的示例场景已经覆盖这三类。

---

## 9. 后续待细化

- 八个核心板块的正式 TypeScript / Zod schema 定义。
- 每类设备的完整 `DeviceSpec` 示例，优先补齐 `conveyor`、`robot`、`workpiece`。
- `SceneTransportSchema`、`SignalBusSchema`、`ExecutableSimGraph` 的最小可运行样例。
- `interface_bindings` 如何从前端已有 `interfaceConfig.interfaces`、`transfer.from/to` 迁移。
- `transport_behaviors` 与具体仿真算法的映射表。
- `SignalBus` 的事件格式和超时策略。
- 隐式拓扑算法如何基于 `physical_interfaces` 做空间推断。
