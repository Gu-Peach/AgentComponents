# SceneBehaviorGraph Runtime 机制问答整理

> 本文整理关于 `event_bus`、`SignalBusRuntime`、`Scheduler`、`trigger / guard / policy`、`resource_locks` 和调度算法的疑问与结论。

---

## 0. 准确性修正与容易混淆点

整理后需要特别修正几处表述：

| 容易混淆的说法 | 更准确的说法 |
|---|---|
| `event_bus` 在执行事件传递。 | `event_bus` 是 `SceneBehaviorGraph` 里的定义；真正执行传递的是 `SignalBusRuntime`。 |
| `RuntimeSnapshot` 负责信号处理。 | `RuntimeSnapshot` 只保存当前状态事实，例如最新信号值、设备状态、资源锁；信号投递由 `SignalBusRuntime` 完成。 |
| 事件路由后直接启动设备行为。 | 事件路由只把事件投递给目标或队列；是否启动行为仍由 `Scheduler` 根据 `trigger / guard / policy` 判断。 |
| `policy` 可以直接存可执行函数。 | `SceneBehaviorGraph.policies` 只存策略类型和参数；可执行逻辑在 Runtime 的 `PolicyLibrary` 中。 |
| `resource_locks` 等同数据库锁。 | 它是仿真语义资源锁，目的不是数据库事务隔离，而是避免动作非法并发；实现上可用内存锁、Redis 原子锁或 CAS。 |
| `when_event / if / then_*` 是当前规则格式。 | 这是旧简写口径；当前模板和案例统一使用 `trigger / guard / policy / action`。 |
| 多个设备同时运行就必须多线程。 | 不必须。第一阶段推荐单线程离散事件仿真，用事件队列和 `active_actions` 表达并发语义。 |

还需要补充四个机制边界：

1. `SignalBusRuntime` 不直接修改业务状态，业务状态更新应通过 `state_transition_rules` 和 `SnapshotManager` 执行。
2. `guard` 表达式不能用不受控的字符串 `eval`，后续实现应选择 JSONLogic、CEL 或受限 DSL。
3. Redis Streams 可用于后续事件流和回放，但第一阶段不要求多进程；单线程内存队列即可表达多设备并发。
4. “并发行为建模”不等于“多线程执行”。两个机械臂同时工作可以表示为两个 `active_actions`，由同一个 Runtime loop 按仿真时间推进。

---

## 1. `event_bus` 到底是什么？

### 问题

`event_bus` 定义的事件注册、路由和投递规则听起来比较抽象。它具体如何运作？底层以什么形式呈现？信号传递逻辑是类似 Vue 的 EventBus，还是发布订阅模式？应该使用什么工具实现？

### 结论

`event_bus` 不是前端 Vue EventBus 那种简单组件通信工具，而是 **场景级领域事件总线定义**。

更准确地说：

```text
SceneBehaviorGraph.event_bus
  定义有哪些事件、事件 payload 长什么样、事件从哪里来、要投递到哪里。

SignalBusRuntime
  在 Runtime 中真正执行 publish / route / deliver。
```
因此二者关系是：

| 层级 | 归属 | 作用 |
|---|---|---|
| `SceneBehaviorGraph.event_bus` | Agent 生成的建模结果 | 事件注册表、路由表、payload 规范、投递语义。 |
| `SignalBusRuntime` | Runtime 内部模块 | 执行事件发布、路由查找、payload 校验、事件投递。 |
| `RuntimeSnapshot.signal_values` | 运行时状态 | 保存某些信号的最新值，不负责传递信号。 |
| `eventQueue / Redis Streams` | 运行时事件流 | 保存事件流动过程，支持调度、推送和回放。 |

### 与 Vue EventBus 的区别

| 对比项 | Vue EventBus | 当前系统的 `event_bus` |
|---|---|---|
| 使用场景 | UI 组件通信 | 工业仿真运行时通信。 |
| 事件定义 | 通常松散 | 必须注册，有 payload schema。 |
| 路由关系 | 谁监听谁收到 | 由 `event_bus.routes` 显式定义。 |
| 状态关系 | 通常不负责状态一致性 | 会触发 `behavior_rules` 和 `state_transition_rules`。 |
| 可复现性 | 通常不保证 | 需要事件序列、时间戳、因果链，支持回放和审计。 |
| 持久化 | 通常不持久化 | 关键事件可落库，高频事件走 Redis / memory。 |

所以它更接近：

```text
发布订阅 Pub/Sub
  + 显式路由表 routing table
  + 领域事件 event envelope
  + 可回放事件流 event stream
```

---

## 2. `event_bus` 底层怎么呈现？

### 建模层

建模层存在于 `SceneBehaviorGraph.event_bus` 中：

```json
{
  "events": [
    {
      "event_id": "main_conveyor_1.pallet_ready",
      "kind": "device_signal",
      "source": "main_conveyor_1",
      "payload_schema": {
        "carrier_id": "string",
        "position": "string"
      },
      "retention": "event_log"
    }
  ],
  "routes": [
    {
      "route_id": "route_pallet_ready_to_sorting",
      "from": "main_conveyor_1.pallet_ready",
      "to": {
        "type": "topic",
        "id": "robot_sorting"
      },
      "delivery": "broadcast"
    }
  ]
}
```

### Runtime 层

Runtime 启动时，会把 `event_bus` 编译成内存索引：

```text
eventRegistry: Map<event_id, event_definition>
routeIndex: Map<event_id, route[]>
eventQueue: Queue<EventEnvelope>
signalValues: Map<signal_id, latest_value>
```

事件在运行时建议包装成 `EventEnvelope`：

```json
{
  "run_id": "run_001",
  "seq": 102,
  "event_id": "main_conveyor_1.pallet_ready",
  "source": "main_conveyor_1",
  "timestamp": 12.5,
  "payload": {
    "carrier_id": "pallet_1",
    "position": "main_conveyor_1.exit"
  },
  "correlation_id": "sort_run_001",
  "causation_id": "action_main_conveyor_transport_001"
}
```

其中：

- `seq` 用于保证同一个 run 内事件顺序。
- `correlation_id` 用于关联同一次业务流程。
- `causation_id` 用于记录该事件由哪个 action 或 event 触发。

---

## 3. 信号传递由谁处理？

### 结论

信号传递由 `SignalBusRuntime` 处理，不由 `RuntimeSnapshot` 处理。

完整链路：

```text
ActionExecutor 执行动作
  -> 动作完成或状态变化产生 effects
  -> effects 中包含 emit event
  -> SignalBusRuntime.publish(event)
  -> 校验 event 是否已在 event_bus.events 注册
  -> 校验 payload 是否符合 payload_schema
  -> 根据 event_bus.routes 找到投递目标
  -> 写入 eventQueue / Redis Streams
  -> 由 SnapshotManager 按 state_transition_rules 更新 RuntimeSnapshot.signal_values 或其他状态
  -> Scheduler 下一轮读取新事件和当前 RuntimeSnapshot
  -> 触发新的 behavior_rules
```

例子：

```text
main_conveyor_1.transport_to_exit 完成
  -> emit main_conveyor_1.pallet_ready

SignalBusRuntime 收到 main_conveyor_1.pallet_ready
  -> 查 routes
  -> 投递到 topic:robot_sorting
  -> Scheduler 找到订阅该 topic 或 trigger 匹配的分拣规则
  -> 两个 robot 根据 policy claim 物料
```

需要注意：

```text
RuntimeSnapshot.signal_values
  只保存“当前某个信号的最新值”。

SignalBusRuntime
  负责“把信号从发送方投递到接收方”，但不直接承担业务状态修改。

SnapshotManager
  根据 state_transition_rules 把事件和 action effects 写回 RuntimeSnapshot。

eventQueue / Redis Streams
  保存“信号或事件的流动过程”。
```

---

## 4. 实现方式建议：单线程离散事件仿真优先

### 结论

第一阶段建议采用 **单线程 Runtime + 离散事件仿真 DES**，而不是一开始就做多线程或多进程。

原因是：

```text
多个设备同时运行、多个信号持续传递
  需要的是“并发仿真语义”，
  不等于底层必须使用多线程。
```

单线程 DES 的好处：

| 优点 | 说明 |
|---|---|
| 可复现 | 同一事件队列和同一优先级规则可以得到确定性结果。 |
| 易调试 | 所有事件按 `simulation_time + seq` 排序，方便回放。 |
| 易解释 | 论文和 Demo 中可以清楚展示每一步事件、状态、动作。 |
| 低复杂度 | 避免多线程竞态、锁竞争、重复 claim、事件乱序。 |

### 第一阶段实现形态

```text
SingleThreadSimulationRuntime
  Scheduler
  ActionExecutor
  SignalBusRuntime
  SnapshotManager
  PolicyLibrary
  EventQueue
  RuntimeSnapshot
```

底层数据结构可以先用内存对象：

```text
eventRegistry: Map<event_id, event_definition>
routeIndex: Map<event_id, route[]>
eventQueue: PriorityQueue<EventEnvelope>(simulation_time, seq)
activeActions: Map<action_id, ActiveAction>
resourceLocks: Map<resource_id, owner_action_id | null>
runtimeSnapshot: RuntimeSnapshot
```

### 多设备并发如何表达

多设备并发不靠多个线程同时跑，而靠 `active_actions` 表达：

```json
{
  "active_actions": {
    "action_robot_1_pick_part_003": {
      "instance_id": "robot_1",
      "behavior_id": "pick_and_place",
      "status": "running",
      "started_at": 10.0,
      "expected_done_at": 13.0
    },
    "action_robot_2_pick_part_004": {
      "instance_id": "robot_2",
      "behavior_id": "pick_and_place",
      "status": "running",
      "started_at": 10.0,
      "expected_done_at": 12.5
    },
    "action_upper_conveyor_transport": {
      "instance_id": "upper_out_conveyor_1",
      "behavior_id": "transport_to_exit",
      "status": "running",
      "started_at": 9.8,
      "continuous": true
    }
  }
}
```

程序虽然是单线程顺序执行，但仿真语义上这些 action 是同时进行的。Runtime loop 只是在每一轮推进仿真时钟、处理到期事件和刷新状态。

### 后续扩展：多进程或可回放版本

如果后续需要支持多 run 并发、服务端水平扩展、前端推送或长期回放，再引入 Redis / WebSocket / Postgres：

| 组件 | 用途 |
|---|---|
| Redis Streams | 保存运行时事件流，例如 `XADD sim:run:{run_id}:events`。 |
| Redis Hash / RedisJSON | 保存 `RuntimeSnapshot`、`signal_values`、`resource_locks`。 |
| WebSocket | 从 Runtime 事件流或 Redis Streams 推送给前端。 |
| Postgres | 保存 `SceneBehaviorGraph`、Agent run、仿真 run、关键事件摘要。 |

多进程是工程化扩展，不是当前案例的必要前提。当前案例应突出：

```text
单线程确定性 Runtime loop
  + 离散事件队列
  + active_actions 表达并发
  + resource_locks 保证互斥
  + SignalBusRuntime 处理事件投递
```

不建议直接把 Vue EventBus 或 Node 原生 `EventEmitter` 当核心实现。它们可以作为内部小工具，但不足以支撑工业仿真的可校验、可回放和可审计要求。

---

## 5. `trigger / guard / policy` 是什么？

### 结论

`trigger / guard / policy / action` 是 `behavior_rules` 的核心结构。

| 字段 | 含义 | 示例 |
|---|---|---|
| `trigger` | 什么事情发生后，规则被唤醒。 | 收到 `robot.pick_request`、状态变化、scheduler tick。 |
| `guard` | 当前状态是否允许执行。 | robot idle、工件池非空、传送带未 blocked、资源未锁。 |
| `policy` | 如果有多个选择或动态决策，如何选。 | 谁空闲谁 claim、选择低负载传送带、资源冲突优先级。 |
| `action` | 条件满足后执行什么。 | 启动设备行为、投递事件、更新状态。 |

推荐写法：

```json
{
  "rule_id": "robot_claim_and_pick",
  "module_id": "parallel_robot_sorting",
  "trigger": {
    "type": "event",
    "event_id": "robot.pick_request"
  },
  "guard": {
    "all": [
      "workpiece_pool.pallet_1.remaining_parts.empty == false",
      "device_states[trigger.payload.robot_id] == idle",
      "target_conveyors.blocked_for_robot(trigger.payload.robot_id) == false"
    ],
    "any": [],
    "none": []
  },
  "policy": {
    "policy_id": "claim_workpiece",
    "inputs": {
      "robot_id": "trigger.payload.robot_id",
      "source_pool": "workpiece_pool.pallet_1.remaining_parts"
    },
    "bind_outputs_to": {
      "material_id": "action.payload.material_id"
    }
  },
  "action": {
    "type": "start_behavior",
    "instance_id": "trigger.payload.robot_id",
    "behavior_id": "pick_and_place",
    "payload": {
      "material_id": "policy.material_id"
    }
  }
}
```

之前的 `when_event / when_state / if / then_*` 只是旧的简写口径，当前模板和案例应统一使用 `trigger / guard / policy / action`。

---

## 6. `trigger / guard / policy` 在哪一阶段产生？

它们由 Agent 在生成 `SceneBehaviorGraph` 时产生，不由 Runtime 临时发明。

对应节点：

```text
EventStateModelerNode
  -> 生成 event_bus 和 state_model。

BehaviorRuleNode
  -> 生成 trigger / guard / action。

PolicySynthesizerNode
  -> 生成 policy 引用、policy 参数和 policies 定义。

ValidationNode
  -> 校验 trigger、guard、policy、action 的引用是否合法。
```

Runtime 阶段只做解释执行：

```text
Scheduler
  -> 用 trigger 找到被唤醒的规则
  -> 用 guard 判断是否可执行
  -> 调用 policy 做动态决策
  -> 执行 action
```

---

## 7. `resource_locks` 是什么？

### 结论

`resource_locks` 是仿真语义里的资源互斥锁。

它有点像操作系统锁，也有点像数据库锁，但目的不是数据库隔离，而是保证仿真动作不会非法并发。

例子：

| 资源 | 互斥含义 |
|---|---|
| `robot_1.gripper` | 同一时刻只能被一个 `pick_and_place` action 占用。 |
| `main_conveyor_1.belt_surface` | 同一时刻只能执行一个主要运输 action。 |
| `pallet_1.slot_001` | 同一物料槽位不能被两个 robot 同时 claim。 |

### 运作机制

```text
Scheduler 找到候选行为
  -> 根据 behavior / action 的 resource_requirements 计算所需资源
  -> 尝试 acquire resource_locks
  -> 全部申请成功才启动 action
  -> 写入 RuntimeSnapshot.resource_locks
  -> action complete / fail / cancel 后 release locks
```

快照中可表示为：

```json
{
  "resource_locks": {
    "robot_1.gripper": {
      "owner_action_id": "action_robot_1_pick_part_003",
      "mode": "exclusive",
      "acquired_at": 12.5
    },
    "upper_out_conveyor_1.belt_surface": null
  }
}
```

### 实现方式

| 场景 | 建议实现 |
|---|---|
| 单进程 Runtime | 内存 `Map` + RuntimeSnapshot 版本号。 |
| 多进程 Runtime | Redis `SET lock_key owner NX PX ttl` 或 Lua 脚本。 |
| 强一致写回 | Snapshot version / CAS，避免两个 action 同时占用同一资源。 |

遗漏点：`resource_locks` 本身只保存锁状态，行为需要哪些资源应来自 `DeviceSpec.runtime_contract`、设备行为定义，或 `SceneBehaviorGraph.behavior_rules[].action.resource_requirements` 的显式声明。

---

## 8. 调度算法是不是应用在 Runtime loop 中？

是的。调度算法就是 Runtime loop 中 `Scheduler` 的核心逻辑。当前基线推荐把 Runtime loop 实现为 **单线程离散事件仿真循环**。

每一轮大致如下：

```text
1. 从 eventQueue 取出当前 simulation_time 下的事件。
2. 读取 RuntimeSnapshot 当前状态。
3. 推进 active_actions，找出到期完成或持续运行的动作。
4. 找到 trigger 命中的 behavior_rules。
5. 检查 guard 是否满足。
6. 调用 policy 做动态决策。
7. 申请 resource_locks。
8. 启动 action，并写入 active_actions。
9. action 到期或状态变化后产生 effects。
10. SignalBusRuntime 投递 emit events。
11. SnapshotManager 按 state_transition_rules 更新 RuntimeSnapshot。
12. CompletionChecker / ObservationEmitter 判断完成或异常。
```

因此：

```text
Agent 阶段
  生成调度规则和策略定义。

Runtime 阶段
  单线程 Scheduler 按离散事件仿真方式解释执行。
```

---

## 9. 单线程 DES 案例：托盘分拣线如何表达并发？

以托盘分拣线为例，虽然有两个机械臂和两条出料传送带同时工作，但 Runtime 可以仍然是单线程。

### 初始阶段

```text
t = 0.0
事件：runtime.sim_start
Scheduler 命中规则：start_pallet_transport
ActionExecutor 启动：main_conveyor_1.transport_to_exit
RuntimeSnapshot.active_actions 写入主传送带动作
```

### 托盘到位

```text
t = 5.0
main_conveyor_1.transport_to_exit 到期完成
ActionExecutor emit main_conveyor_1.pallet_ready
SignalBusRuntime 投递 pallet_ready
Scheduler 启用 parallel_robot_sorting 模块
```

### 两个机械臂并发分拣

```text
t = 5.1
Scheduler 发现 robot_1 idle、robot_2 idle、工件池非空
PolicyLibrary.claim_workpiece 分别为 robot_1 / robot_2 原子 claim 不同物料
ActionExecutor 启动两个 pick_and_place action
```

此时单线程 RuntimeSnapshot 中会出现多个同时运行的动作：

```json
{
  "clock": 5.1,
  "active_actions": {
    "action_robot_1_pick_part_001": {
      "instance_id": "robot_1",
      "behavior_id": "pick_and_place",
      "status": "running",
      "expected_done_at": 8.1
    },
    "action_robot_2_pick_part_002": {
      "instance_id": "robot_2",
      "behavior_id": "pick_and_place",
      "status": "running",
      "expected_done_at": 7.6
    }
  }
}
```

这里的“同时运行”是仿真语义，不是两个 OS 线程。Runtime loop 下一步会跳到最近的 `expected_done_at = 7.6`，先处理 robot_2 完成事件，再继续推进。

### 出料传送带 backpressure

```text
t = 7.6
robot_2.pick_and_place 完成
SignalBusRuntime emit output_conveyor.material_arrived
SnapshotManager 增加 lower_out_conveyor_1.current_load
PolicyLibrary.backpressure 判断 current_load 是否超过 max_capacity
```

如果超载：

```text
emit conveyor.blocked
SignalBusRuntime 投递 blocked
Scheduler 命中 blocked_conveyor_pauses_robot
emit robot.pause_pick
后续 robot 不再 claim 目标传送带已 blocked 的新物料
```

如果负载下降：

```text
emit conveyor.capacity_available
Scheduler 命中 capacity_available_resumes_robot
emit robot.resume_pick
robot 重新进入 claim 物料流程
```

### 这个案例体现的 DES 特点

| DES 要素 | 在案例中的体现 |
|---|---|
| 离散事件 | `sim_start`、`pallet_ready`、`pick_done`、`blocked`、`capacity_available`。 |
| 仿真时钟 | `clock` 跳到下一个事件时间，不需要真实等待。 |
| 并发动作 | 多个 action 同时存在于 `active_actions`。 |
| 确定性调度 | 同一时间多个事件按 `seq` 或确定性优先级处理。 |
| 资源互斥 | `resource_locks` 防止重复 claim 和设备资源冲突。 |

结论：当前案例需要的是 **单线程 DES 表达多设备并发**，不是多线程 Runtime。

---

## 10. 是否有可改造的现成调度算法？

有，但不建议直接套一个重型框架。当前最适合的是以离散事件仿真 DES 为主线的组合式方案：

```text
离散事件仿真 DES
  + 规则引擎 Rule Engine
  + 资源约束调度 Resource-Constrained Scheduling
  + 少量 Petri Net 思想用于死锁检测
```

| 方法 | 可借鉴部分 |
|---|---|
| 离散事件仿真 DES | Runtime loop、事件队列、仿真时钟、事件驱动执行。 |
| Rule Engine | `trigger + guard -> action` 的规则匹配。 |
| Resource-Constrained Project Scheduling | 多设备、多资源互斥时的调度选择。 |
| Petri Net | token / transition 思想适合可达性和死锁检测。 |
| Behavior Tree | 适合表达设备局部行为，但不适合作为整个场景总模型。 |
| HTN / GOAP | 适合 Agent 规划任务分解，Runtime 阶段不建议过重。 |

可参考工具：

| 技术栈 | 工具 | 适用点 |
|---|---|---|
| TypeScript | `json-rules-engine` | 可借鉴规则判断，但资源调度要扩展。 |
| TypeScript | `XState` | 适合设备 FSM，不适合作为整个场景总线。 |
| TypeScript | BullMQ / Redis Streams | 适合事件队列和异步任务流。 |
| TypeScript | `async-mutex` | 适合单进程资源锁。 |
| Redis | `SET NX` / Lua | 适合分布式资源锁。 |
| Python | SimPy | 典型离散事件仿真框架，适合参考机制。 |
| Python | durable_rules | 规则引擎思路可参考。 |

建议第一阶段实现领域化轻量 Scheduler：

```text
规则匹配：自己实现 rule matcher。
事件队列：第一阶段使用内存 PriorityQueue，后续可扩展到 Redis Streams。
guard 表达式：JSONLogic / CEL / 自定义 DSL。
policy：Runtime 内置 PolicyLibrary。
资源锁：第一阶段使用内存锁，后续多进程再扩展到 Redis 原子锁。
设备 FSM：参考 XState 思想或轻量状态机实现。
```

---

## 11. 策略函数应该存在哪里？

策略分成“定义”和“实现”。

```text
策略定义
  存在 SceneBehaviorGraph.policies。

策略实现
  存在 Runtime 的 PolicyLibrary 代码里。
```

不建议把任意可执行代码直接存进数据库，这样不安全，也不可控。

推荐在 `SceneBehaviorGraph.policies` 中保存策略类型和参数：

```json
{
  "policies": {
    "claim_workpiece": {
      "type": "shared_pool_claim",
      "source_pool": "workpiece_pool.pallet_1.remaining_parts",
      "workers": ["robot_1", "robot_2"],
      "selection": "next_available_material",
      "mutual_exclusion": true
    },
    "backpressure": {
      "type": "capacity_threshold",
      "blocked_when": "current_load >= max_capacity",
      "resume_when": "current_load <= resume_threshold"
    }
  }
}
```

Runtime 中由可信代码实现：

```text
PolicyLibrary.shared_pool_claim(...)
PolicyLibrary.capacity_threshold(...)
PolicyLibrary.resource_lock(...)
PolicyLibrary.deadlock_detection(...)
```

三者边界：

| 模块 | 保存什么 |
|---|---|
| `SceneBehaviorGraph.policies` | 用哪个策略、参数是什么。 |
| `Runtime PolicyLibrary` | 策略具体怎么算。 |
| `RuntimeSnapshot` | 策略执行后的状态和中间结果。 |

---

## 12. 最终链路总结

```text
Agent 生成 SceneBehaviorGraph
  -> 定义事件、路由、规则、状态、策略。

Runtime 初始化 RuntimeSnapshot
  -> 保存当前设备、物料、信号、锁和动作状态。

单线程 Scheduler 每轮读取 SceneBehaviorGraph + RuntimeSnapshot
  -> 按离散事件队列推进仿真时钟
  -> 用 trigger 找规则
  -> 用 guard 判断能不能执行
  -> 用 policy 做动态选择
  -> 用 resource_locks 保证资源互斥
  -> 启动 action

ActionExecutor 执行动作
  -> 产生 effects 和 emit events。

SignalBusRuntime
  -> 把 emit 出来的事件按 event_bus.routes 投递出去。

SnapshotManager
  -> 把事件和动作结果更新回 RuntimeSnapshot。
```

一句话理解：

```text
SceneBehaviorGraph = 行为程序
RuntimeSnapshot = 当前运行状态
Scheduler = 单线程 DES 行为解释器 / 调度器
SignalBusRuntime = 事件总线 / 信号中间件
PolicyLibrary = 策略函数库
ActionExecutor = 设备行为执行器
```
