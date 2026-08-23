# 设备数据结构定义

> 版本：v0.1  
> 日期：2026-08-20  
> 阶段：业务逻辑梳理 / 设备结构建模  
> 背景：参考 Visual Components 的组件行为、接口、信号、Process Flow、Transport/Flow 思路，定义本系统自己的设备结构。

---

## 论文视角：行为仿真的建模起点

本文档中的所有 schema 组合起来，可以理解为一个面向三维工业场景的 **工艺行为建模体系**。它不是为了单纯保存前端场景，而是为了让 Agent 和 Simulation Runtime 能够理解：场景中有哪些设备、物料按什么工艺流转、设备之间如何连接和通讯、某个运行状态下设备可以执行哪些行为。

因此，基于 Agent 的行为仿真可以先拆成两个建模问题：

| 建模问题 | 关注对象 | 产物 |
|---|---|---|
| 工艺层行为建模 | 整个工艺场景如何运行，物料如何流转，设备之间如何协作，信号和状态如何传播。 | `SceneDocument`、`SceneTransportSchema`、`SignalBusSchema`、`SimPlan`、`ExecutableSimGraph` |
| 设备层行为建模 | 单台设备为了参与上述工艺仿真，必须暴露哪些标准化能力和运行契约。 | `DeviceSpec`、`physical_interfaces`、`process_ports`、`signal_ports`、`transport_behaviors`、`runtime_contract` |

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

---

## 0. 总览：分层与运行链路

本文档后续所有字段定义都围绕一个原则展开：**设备能力、场景事实、计划目标、运行状态必须分层表达，不能混成一个大对象。**

当前建议拆成八个核心板块：

| 板块 | 类型 | 归属 | 说明 |
|---|---|---|---|
| `DeviceSpec` | 设备级 schema | Postgres / 设备库 | 定义设备天生具备的参数、物理连接接口、流程口、信号口和 Transport / Flow 行为能力。 |
| `SceneDocument` | 场景级事实 schema | Postgres / 场景文档 | 定义场景中有哪些设备实例，以及设备实例之间的 process、physical、signal 关系。 |
| `SceneTransportSchema` | 场景级派生 schema | 可缓存 / 可重建 | 根据 `DeviceSpec + SceneDocument` 编译出当前场景中理论上可能发生的物料流转和 transport 行为拓扑。 |
| `SignalBusSchema` | 信号级派生 schema | 可缓存 / 可重建 | 根据设备信号口、场景信号边和 `SimPlan` 编译出信号路由、等待规则、payload 约束和超时策略。 |
| `SimPlan` | Agent 计划产物 | Postgres / Agent run | Agent 根据用户目标、场景和设备能力生成的本次仿真计划。 |
| `ExecutableSimGraph` / `RuntimePlan` | 可执行计划 | Simulation Runtime 派生 | Runtime 将 `SimPlan` 编译成可执行描述，包括步骤前置条件、等待条件、资源锁、输入信号、输出信号、完成效果和失败策略。 |
| `RuntimeSnapshot` | 运行时状态 | Redis / Runtime memory，关键事件落 Postgres | 保存当前 signal value、设备 FSM、物料位置、等待队列、资源锁、active action 和仿真时钟。 |
| `DeviceRuntimeProfile` | 当前设备行为画像 | Runtime 派生 / 可推送前端 | 根据 `ExecutableSimGraph + RuntimeSnapshot` 实时计算某个设备实例当前可执行、等待、阻塞或正在执行哪些行为。 |

最重要的边界是：

```text
DeviceSpec 描述“设备天生能做什么”；
SceneDocument 描述“这个场景里有什么、怎么连”；
SceneTransportSchema 描述“这个场景理论上能怎么流转”；
SimPlan 描述“这次仿真计划要做什么”；
ExecutableSimGraph 描述“这次计划如何被 Runtime 执行”；
RuntimeSnapshot 描述“当前真实运行到什么状态”；
DeviceRuntimeProfile 描述“这个设备此刻真的能做什么”。
```

完整运行链路如下：

```text
DeviceSpec + SceneDocument
  -> SceneTransportSchema

DeviceSpec.signal_ports + SceneDocument.signal_edges + SimPlan
  -> SignalBusSchema

Agent(SceneDocument + DeviceSpec + 用户目标 + 可选 RuntimeSnapshot)
  -> SimPlan

Runtime(SimPlan + SceneTransportSchema + SignalBusSchema)
  -> ExecutableSimGraph / RuntimePlan

ExecutableSimGraph + RuntimeSnapshot
  -> DeviceRuntimeProfile

Scheduler(DeviceRuntimeProfile)
  -> 执行动作 / 发出信号 / 更新 RuntimeSnapshot / 推送事件
```

因此，`DeviceRuntimeProfile` 不是场景事实源，也不是长期保存的设备 schema。它是运行时动态视图，会随着 `RuntimeSnapshot` 的变化持续更新。真正的场景级可执行能力描述应命名为 `SceneTransportSchema`。

---

## 1. 核心判断

设备在本系统中不是一个单纯的 GLB 文件，而是一个可被布置、连接、规划、调度和仿真的业务实体。

因此，一个设备至少需要包含四层结构：

```text
Device
  ├─ Interface / Connector 层
  ├─ Signal 层
  ├─ Process Flow 层
  └─ Transport / Flow 行为层
```

四层之间的关系：

```text
Process Flow
  ↓ 定义物料/产品工艺路线
Interface / Connector
  ↓ 编译流程口到真实接口、坐标和连接兼容性
Transport / Flow 行为
  ↓ 执行实际搬运、转入、转出、等待完成
Signal
  ↔ 在运行时协调启动、等待、阻塞、完成、超时
```

接口之间形成一个“工艺意图 → 运行协调 → 物理执行”的协作链。
简化理解：

```text
Process Flow：产品应该去哪儿
Interface：设备从哪里接、从哪里出
Transport / Flow：产品怎么真的过去
Signal：运行时谁等谁、谁通知谁
```

---

## 2. 四层定义

### 2.1 Interface / Connector 层

这一层解决结构连接问题。

它回答：

- 两个设备在物理或逻辑上能不能连接？
- 从哪个接口连到哪个接口？
- 接口方向是否兼容？
- 物料类型是否兼容？
- 真实坐标、方向、锚点是否能被执行层使用？

业务含义：

```text
Interface / Connector 是设备的连接能力，不是工艺流程本身，也不是运行时信号。
```

本系统中拆成两类：

| 类型                  | 作用                                                | 是否给普通用户直接展示            |
| --------------------- | --------------------------------------------------- | --------------------------------- |
| `physical_interfaces` | 真实接口，带坐标、方向、node_name，用于对齐和执行。 | 默认不直接展示，调试模式可展示。  |
| `process_ports`       | 流程层抽象口，只表达 Input / Output。               | 展示给用户在 Interface 画布连线。 |

示例：

```json
{
  "physical_interfaces": [
    {
      "interface_id": "exit",
      "kind": "material",
      "direction": "output",
      "node_name": "ExitAnchor",
      "local_position": [1.0, 0.0, 0.4],
      "local_forward": [1.0, 0.0, 0.0],
      "material_classes": ["box", "pallet"]
    }
  ],
  "process_ports": [
    { "port_id": "flow_input", "direction": "input", "label": "Input" },
    { "port_id": "flow_output", "direction": "output", "label": "Output" }
  ]
}
```

---

### 2.2 Signal 层

Signal 层不是普通物理接口。它是一种运行时通信与事件机制。

它回答：

- 设备什么时候通知其他设备？
- 某个设备是否 busy？
- 某个动作是否 done？
- 物料到达出口后，谁被触发？
- 下游设备忙时，上游物料是否等待？
- 等待超时后是否触发异常？

Signal 层必须分清“定义、编排、派生运行结构、当前运行状态”四个层级。这里最关键的规则是：**设备级 schema 中只包含 `signal_ports`，不包含 `signal_edges`。**

| 层级 | 结构 | 归属 | 说明 |
|---|---|---|---|
| 设备级 schema | `signal_ports` | `DeviceSpec` | 定义单台设备自身能发出/接收哪些信号。 |
| 场景级 schema | `signal_edges` | `SceneDocument` | 根据场景中选用的设备实例，定义设备间信号如何连接。 |
| 信号级运行 schema | `SignalBusSchema` | 由场景级 schema 编译/派生 | 结合设备信号端口和场景信号连接，生成运行时可消费的信号路由、等待条件、payload 约束、超时规则。 |
| 运行时状态 | `SignalBusState`、`DeviceFSM`、`WaitQueue` | Simulation Runtime / Redis | 保存当前信号值、设备状态、等待队列、资源锁等瞬时状态。 |

也就是说：

```text
DeviceSpec.signal_ports
  + SceneDocument.signal_edges
  + SimPlan.signal_rules
  -> SignalBusSchema
  -> SignalBusState + DeviceFSM + WaitQueue
```

设备级 schema 示例：

```json
{
  "signal_ports": [
    { "port_id": "start_pick", "direction": "input", "value_type": "event" },
    { "port_id": "busy", "direction": "output", "value_type": "boolean" },
    { "port_id": "done", "direction": "output", "value_type": "event" }
  ]
}
```

场景级 schema 示例：

```json
{
  "signal_edges": [
    {
      "edge_id": "sig_edge_001",
      "source": "conveyor_1.part_ready",
      "target": "robot_1.start_pick",
      "edge_type": "control_signal"
    },
    {
      "edge_id": "sig_edge_002",
      "source": "robot_1.done",
      "target": "conveyor_1.release_waiting_material",
      "edge_type": "release_signal"
    }
  ]
}
```

信号级运行 schema 示例：

```json
{
  "signal_bus_schema": {
    "routes": [
      {
        "route_id": "route_001",
        "source_signal": "conveyor_1.part_ready",
        "target_signal": "robot_1.start_pick",
        "payload_schema": { "material_id": "string" },
        "timeout_s": 10,
        "on_timeout": "emit_observation"
      }
    ],
    "wait_rules": [
      {
        "condition": "robot_1.busy == true",
        "waiting_location": "conveyor_1.exit",
        "queue_id": "conveyor_1.exit_queue",
        "release_on": "robot_1.done"
      }
    ]
  }
}
```

运行时状态不要写进场景事实：

```json
{
  "robot_1.busy": true,
  "conveyor_1.exit_queue": ["box_001"]
}
```

这些状态属于 Simulation Runtime / Redis，而不是长期 SceneDocument，也不是 DeviceSpec。

#### 2.2.1 Signal 层的生成关系

Signal 相关结构不是一次性手写完整的，而是由上游 schema 逐步约束出来：

```text
1. 设备级 schema：
   robot 说明自己有 busy / done / start_pick
   conveyor 说明自己有 part_ready / blocked / release_waiting_material

2. 场景级 schema：
   当前场景用了 robot_1 和 conveyor_1
   场景声明 conveyor_1.part_ready -> robot_1.start_pick
   场景声明 robot_1.done -> conveyor_1.release_waiting_material

3. 信号级运行 schema：
   系统根据设备 signal_ports + 场景 signal_edges 编译 SignalBusSchema
   SignalBusSchema 说明信号路由、payload、等待条件、超时策略

4. 运行时状态：
   SignalBus 根据 SignalBusSchema 分发事件
   DeviceFSM 根据收到的信号切换 idle / busy / waiting / error
   WaitQueue 根据设备 busy / done 等状态决定物料等待或释放
```

因此更准确的业务说法是：

```text
设备拥有信号能力；
场景规定信号关系；
SignalBusSchema 编译信号通讯规则；
SignalBus + DeviceFSM + WaitQueue 执行实时通讯。
```

这里的 `SignalBusSchema` 可以理解为“信号级 schema”，但它不是用户手工维护的第一事实，而是由设备级 schema、场景级 schema 和 SimPlan 编译出来的运行时契约。这个命名可以保留，因为它很好地表达了“信号通讯规则已经从场景中被编译出来，可以交给 runtime 执行”。

---

### 2.3 Process Flow 层

Process Flow 层解决工艺路线问题。

它回答：

- 物料从哪个设备开始？
- 中间经过哪些设备？
- 最终到哪个设备？
- 用户在流程画布上连出的工艺顺序是什么？

业务含义：

```text
Process Flow 是用户可理解的工艺路线，不负责真实坐标、轨迹、信号等待和资源锁。
```

示例：

```json
{
  "process_edges": [
    {
      "edge_id": "proc_edge_001",
      "source_instance_id": "conveyor_1",
      "source_interface": "flow_output",
      "target_instance_id": "robot_1",
      "target_interface": "flow_input",
      "edge_type": "material_flow"
    },
    {
      "edge_id": "proc_edge_002",
      "source_instance_id": "robot_1",
      "source_interface": "flow_output",
      "target_instance_id": "conveyor_2",
      "target_interface": "flow_input",
      "edge_type": "material_flow"
    }
  ]
}
```

这表达的是：

```text
conveyor_1 -> robot_1 -> conveyor_2
```

它还没有表达：

- robot 如何抓取？
- conveyor 出口坐标在哪里？
- robot busy 时 conveyor 是否等待？
- 物料是否已经到达？

这些属于 Interface、Transport / Flow 和 Signal 层。

---

### 2.4 Transport / Flow 行为层

Transport / Flow 行为层解决实际执行问题。

它回答：

- 设备有哪些可执行行为？
- 物料如何转入、转出？
- 使用哪个运动算法？
- 动作开始条件是什么？
- 动作完成后产生什么效果？
- 下游忙时是否等待？
- 是否需要容量检查？

业务含义：

```text
Transport / Flow 是行为能力，不是接口。它使用接口、信号和流程来完成实际物料移动。
```

这里需要再分清两类结构：

| 层级 | 结构 | 归属 | 说明 |
|---|---|---|---|
| 设备级行为能力 | `transport_behaviors` / `transport_capabilities` | `DeviceSpec` | 定义设备本身会做什么，例如输送、抓取、放置、入库、出库。 |
| 本次仿真行为绑定 | `transport_steps` / `DeviceRuntimeProfile` | `SimPlan` + Simulation Runtime 派生 | 结合工艺路线、连接关系、信号关系和当前状态，决定这次仿真中设备实例实际可以执行哪些行为。 |

因此更准确的业务关系是：

```text
DeviceSpec.transport_behaviors
  + DeviceSpec.signal_ports
  + DeviceSpec.process_ports / interface_bindings
  + SceneDocument.process_edges / physical_edges / signal_edges
  + SimPlan.goal / process_route / signal_rules
  + RuntimeSnapshot.signal_values / fsm_states / resource_locks / material_locations
  -> DeviceRuntimeProfile
  -> enabled_behaviors / blocked_behaviors / waiting_behaviors / executing_behavior
```

也就是说，设备规格只声明“我能做什么”；场景和仿真计划声明“这次需要我怎么参与”；运行时状态再决定“这一刻我能不能真的开始做”。

`Transport / Flow` 不等于某次仿真的最终行为列表。它更像是行为能力库。真正用于调度器执行的是编译后的 `DeviceRuntimeProfile`。

示例：

```json
{
  "transport_behaviors": [
    {
      "behavior_id": "pick_and_place",
      "behavior_type": "material_transfer",
      "input_physical_interface": "pick_area",
      "output_physical_interface": "place_area",
      "default_algorithm": "robot_pick_place",
      "input_signals": ["start_pick"],
      "output_signals": ["busy", "done"],
      "fsm_states": ["idle", "busy", "error"],
      "preconditions": [
        { "type": "device_state", "state": "idle" },
        { "type": "material_at", "location": "pick_area" }
      ],
      "effects": [{ "type": "material_at", "location": "place_area" }]
    }
  ]
}
```

本次仿真中，系统可以把上述能力编译成设备运行行为画像：

```json
{
  "device_instance_id": "robot_1",
  "spec_id": "spec_robot_v1",
  "runtime_profile_id": "profile_robot_1_run_001",
  "capable_behaviors": ["pick_and_place"],
  "candidate_behaviors": [
    {
      "behavior_id": "pick_and_place",
      "bound_process_edge": "proc_edge_001",
      "bound_physical_input": "conveyor_1.exit",
      "bound_physical_output": "conveyor_2.entry",
      "subscribed_signals": ["conveyor_1.part_ready", "robot_1.start_pick"],
      "emitted_signals": ["robot_1.busy", "robot_1.done", "robot_1.error"],
      "guards": [
        "robot_1.fsm_state == idle",
        "material_at(conveyor_1.exit)",
        "signal(conveyor_1.part_ready) == true",
        "resource(robot_1.gripper).locked_by == null"
      ],
      "on_start": ["set robot_1.busy = true", "lock robot_1.gripper"],
      "on_complete": ["emit robot_1.done", "unlock robot_1.gripper", "move material to conveyor_2.entry"],
      "on_blocked": ["enqueue material at conveyor_1.exit_queue"],
      "current_status": "waiting_signal"
    }
  ]
}
```

这个结构适合放在仿真运行时内存 / Redis 中，也可以在 Postgres 中保存摘要用于审计和回放，但不应作为手工维护的设备源数据。

---

## 3. Process Flow 和 Transport / Flow 的区别

一句话：

```text
Process Flow 是路线。
Transport / Flow 是执行路线的能力。
```

| 对比项       | Process Flow                          | Transport / Flow 行为                         |
| ------------ | ------------------------------------- | --------------------------------------------- |
| 关注点       | 工艺步骤、流转顺序、用户意图          | 物料实际移动、等待、转运、完成                |
| 是否面向用户 | 是                                    | 通常否，更多面向运行时和 Agent                |
| 是否关心坐标 | 不直接关心                            | 需要真实接口和轨迹锚点                        |
| 是否关心信号 | 不直接关心                            | 需要信号触发和等待机制                        |
| 示例         | `conveyor_1 -> robot_1 -> conveyor_2` | `robot_1 wait part_ready then pick_and_place` |

业务示例：

```text
Process Flow：
  conveyor_1 -> robot_1 -> conveyor_2

Transport / Flow：
  conveyor_1 将 box 运到 exit
  conveyor_1 发出 part_ready
  robot_1 如果 idle，则 start_pick
  robot_1 busy=true
  robot_1 抓取 box 并放到 conveyor_2.entry
  robot_1 done
  conveyor_1 释放等待队列中的下一个 box
```

---

## 4. 四层协作流程

### 4.1 用户创建流程

```text
用户在前端 Interface 画布连接：
  conveyor_1.flow_output -> robot_1.flow_input
```

产生 `process_edges`：

```json
{
  "source": "conveyor_1.flow_output",
  "target": "robot_1.flow_input"
}
```

### 4.2 后端编译接口

通过 `interface_bindings` 编译：

```text
conveyor_1.flow_output -> conveyor_1.exit
robot_1.flow_input -> robot_1.pick_area
```

产生 `physical_edges`：

```json
{
  "source": "conveyor_1.exit",
  "target": "robot_1.pick_area",
  "compiled_from": "proc_edge_001"
}
```

### 4.3 Agent 生成执行计划

Agent 读取：

- `process_edges`
- `physical_edges`
- `signal_edges`
- `signal_ports`
- `process_ports`
- `interface_bindings`
- `transport_behaviors`
- 当前拓扑摘要

生成 `SimPlan`：

```json
{
  "actions": [
    {
      "action_id": "a1",
      "device_id": "conveyor_1",
      "action_type": "transport_to_exit",
      "output_signals": ["part_ready"]
    },
    {
      "action_id": "a2",
      "device_id": "robot_1",
      "action_type": "pick_and_place",
      "trigger": { "signal": "conveyor_1.part_ready" },
      "output_signals": ["busy", "done"]
    }
  ]
}
```

`SimPlan` 仍然是计划，不是设备当前行为状态。进入运行前，Simulation Runtime 需要继续编译：

```text
SimPlan
  + DeviceSpec
  + SceneDocument
  + SignalBusSchema
  + RuntimeSnapshot
  -> DeviceRuntimeProfile
```

`DeviceRuntimeProfile` 会回答每个设备实例在本次仿真中：

- 会接收哪些状态和信号；
- 这些状态来自哪个上游设备、哪个 signal edge 或哪个物理接口；
- 哪些 `transport_behaviors` 被本次计划实际使用；
- 每个行为的启动条件、阻塞条件、等待队列、资源锁和完成事件是什么；
- 当前行为是 `enabled`、`waiting_signal`、`blocked`、`executing` 还是 `completed`。

### 4.4 Runtime 编译可激活行为

```text
conveyor_1.transport_to_exit
  需要：material_at(conveyor_1.entry)
  输出：conveyor_1.part_ready

robot_1.pick_and_place
  需要：conveyor_1.part_ready + robot_1.idle + material_at(conveyor_1.exit)
  输出：robot_1.busy / robot_1.done

conveyor_2.accept_material
  需要：material_at(conveyor_2.entry) + conveyor_2.capacity_available
  输出：conveyor_2.material_accepted
```

调度器真正消费的是这组可激活行为，而不是直接消费 LLM 文本或手写规则。

### 4.5 Runtime 实时执行

```text
conveyor_1 运行
box 到达 conveyor_1.exit
SignalBus 发出 conveyor_1.part_ready
robot_1 idle -> start_pick
robot_1 busy=true
如果下一个 box 到达 conveyor_1.exit 且 robot_1 busy=true
  conveyor_1.exit_queue 加入 box_002
robot_1 done
SignalBus 发出 robot_1.done
conveyor_1.release_waiting_material
```

普通信号流转不调用 Agent。只有超时、死锁、目标状态未达成、用户打断时，Runtime 才把 observation 发给 Agent。

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
  ]
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

- Process Flow 不做物理执行。
- Signal 不做工艺路线。
- Transport / Flow 不做用户意图表达。
- Interface / Connector 不做运行时决策。

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

- 每类设备的完整 `DeviceSpec` 示例。
- `interface_bindings` 如何从前端已有 `interfaceConfig.interfaces`、`transfer.from/to` 迁移。
- `transport_behaviors` 与具体仿真算法的映射表。
- `SignalBus` 的事件格式和超时策略。
- 隐式拓扑算法如何基于 `physical_interfaces` 做空间推断。
