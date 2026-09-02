# Runtime Scheduler 系统设计思路

> 阶段：后续 Runtime 系统开发参考
> 当前定位：本文只总结 Runtime Scheduler 的职责、模块拆分和算法边界，不表示当前 Agent 已实现 Runtime。

---

## 1. 核心定位

当前系统采用“离线 Agent 建模 + 在线 Runtime 调度”的双层架构：

```text
DeviceSpec + SceneDocument + 用户目标
  -> LangGraph Agent
  -> SceneBehaviorGraph

SceneBehaviorGraph + RuntimeSnapshot
  -> Runtime Scheduler
  -> 事件投递、规则匹配、策略执行、资源仲裁、行为执行、状态更新
```

其中：

- `Agent` 负责生成 `SceneBehaviorGraph`。
- `SceneBehaviorGraph` 描述场景应该如何运行。
- `RuntimeSnapshot` 保存当前运行时状态事实。
- `Runtime Scheduler` 负责真正执行行为图。

一句话：

> Runtime Scheduler 是 `SceneBehaviorGraph` 的在线执行引擎，不是 Agent 的一部分。

---

## 2. Runtime Scheduler 不是单一算法

Runtime Scheduler 可以理解为一个大型调度系统，而不是一个单一 `schedule()` 算法。

它由多种执行能力组合而成：

```text
Runtime Scheduler
  = DES 事件推进
  + event_bus 事件投递
  + behavior_rules 规则匹配
  + guard 条件过滤
  + policy 算法执行
  + resource_locks 资源仲裁
  + action 调度派发
  + state_transition 状态更新
  + failure_observation 异常检测
  + completion_conditions 完成判断
```

因此，它更像：

```text
SceneBehaviorGraph Execution Engine
```

或者：

```text
Event-driven Runtime Scheduler
```

---

## 3. 与 Agent 的边界

| 问题 | Agent 负责 | Runtime Scheduler 负责 |
|---|---|---|
| 场景应该如何运行 | 生成 `SceneBehaviorGraph` | 按行为图执行 |
| 有哪些事件和路由 | 生成 `event_bus` | 投递事件、展开 topic、写事件日志 |
| 哪些规则可触发行为 | 生成 `behavior_rules` | 运行时匹配 trigger、guard、policy |
| 哪些策略可用 | 生成 policy 声明和参数 | 执行具体策略算法 |
| 资源冲突如何表达 | 生成 `resource_locks` 相关规则和策略声明 | 实时申请、释放、等待、仲裁资源 |
| 设备状态如何变化 | 生成 `state_transition_rules` | 写入 `RuntimeSnapshot` |
| 异常如何观测 | 生成 `failure_observations` | 运行时检测并 emit observation |
| 完成条件是什么 | 生成 `completion_conditions` | 运行时判定是否完成 |

关键结论：

> Agent 生成策略声明；Runtime Scheduler 实现并执行策略算法。

---

## 4. 输入与输出

### 4.1 输入

Runtime Scheduler 的主要输入：

| 输入 | 说明 |
|---|---|
| `SceneBehaviorGraph` | Agent 生成的场景行为图，包含事件、规则、策略、状态迁移、完成条件等。 |
| `RuntimeSnapshot` | 当前运行状态，包括设备状态、物料位置、资源锁、信号值、队列、active actions。 |
| `SceneDocument.materials` | 初始化物料状态时使用。 |
| `DeviceSpec.runtime_contract` | 设备状态机、资源、容量等运行时约束。 |

### 4.2 输出

Runtime Scheduler 的主要输出：

| 输出 | 说明 |
|---|---|
| 更新后的 `RuntimeSnapshot` | 当前设备状态、物料状态、资源锁、队列、active actions。 |
| 事件日志 | 已发生事件、投递结果、topic 展开记录。 |
| action 执行记录 | 行为开始、完成、失败、耗时等。 |
| observation | 死锁、超载、资源冲突、超时等异常观测。 |
| completion result | 仿真完成、失败、暂停、终止等结果。 |

---

## 5. 推荐模块拆分

```text
runtime/
  event_queue/
    event_queue.py
  signal_bus/
    signal_bus_runtime.py
  scheduler/
    rule_matcher.py
    guard_evaluator.py
    priority_scheduler.py
    action_dispatcher.py
  policy_executor/
    shared_pool_claim.py
    backpressure.py
    queue_wait.py
    stop_point_selection.py
    resource_lock.py
    deadlock_detection.py
  state/
    snapshot_manager.py
    effect_applier.py
  observation/
    observation_emitter.py
  completion/
    completion_checker.py
```

---

## 6. 模块职责

### 6.1 `event_queue`

负责离散事件仿真中的事件队列和仿真时间推进。

职责：

- 维护 pending events。
- 按时间戳、优先级、确定性 tie-breaker 排序。
- 推进 simulation time。
- 支持 immediate event 和 future event。

可参考 DES 的 next-event time advance 思路。

### 6.2 `signal_bus`

负责执行 `SceneBehaviorGraph.event_bus`。

职责：

- 校验事件是否注册在 `event_bus.events`。
- 校验 payload 是否符合 `payload_schema`。
- 根据 `routes` 找到投递目标。
- 展开 `topic` 和 `subscriptions`。
- 生成投递给 rule / runtime module 的事件项。
- 写入事件日志或 `RuntimeSnapshot.signal_values`。

示例：

```text
main_conveyor_1.pallet_ready
  -> route_pallet_ready_to_robot_pick_topic
  -> topic robot_pick_request
  -> subscriptions.robot_pick_request
  -> robot.pick_request { robot_id: robot_1 }
  -> robot.pick_request { robot_id: robot_2 }
```

### 6.3 `scheduler`

负责从事件和当前状态中选择可执行行为。

职责：

1. 根据事件匹配 `behavior_rules.trigger`。
2. 调用 `GuardEvaluator` 检查 `guard`。
3. 调用 `PolicyExecutor` 执行策略。
4. 调用资源锁模块申请资源。
5. 多候选规则同时可执行时做确定性排序。
6. 生成 action dispatch request。

### 6.4 `policy_executor`

负责执行具体策略算法。

Agent 生成的是：

```json
"policy": {
  "policy_id": "claim_workpiece",
  "inputs": {
    "robot_id": "trigger.payload.robot_id",
    "source_pool": "workpiece_pool.remaining_parts"
  }
}
```

Runtime 需要实现的是：

```text
claim_workpiece(snapshot, robot_id, source_pool)
```

也就是说，Runtime 要把 `policy_id` 映射到真实策略算法。

### 6.5 `state`

负责维护 `RuntimeSnapshot`。

职责：

- 应用 `state_transition_rules.effects`。
- 写入设备状态。
- 写入物料位置。
- 写入资源锁。
- 写入队列和传送带断点占用。
- 维护 active actions。

### 6.6 `observation`

负责异常观测。

典型 observation：

- `observation.deadlock_detected`
- `observation.resource_conflict`
- `observation.overload_detected`
- `observation.action_timeout`
- `observation.claim_conflict_detected`

### 6.7 `completion`

负责判断仿真是否完成。

输入：

- `completion_conditions`
- `RuntimeSnapshot`
- `active_actions`
- 事件队列状态

输出：

- `global.sorting_done`
- run status: `completed / failed / paused / stopped`

---

## 7. 核心运行循环

推荐采用单线程离散事件仿真作为基线。

```text
Runtime 初始化 RuntimeSnapshot
  -> emit runtime.sim_start
  -> EventQueue 取出下一个事件
  -> SignalBusRuntime 投递事件
  -> Scheduler 匹配 behavior_rules
  -> GuardEvaluator 过滤不可执行规则
  -> PolicyExecutor 执行策略函数
  -> ResourceManager 申请资源锁
  -> PriorityScheduler 排序候选 action
  -> ActionDispatcher 启动或推进行为
  -> EffectApplier 应用 state_transition_rules
  -> SnapshotManager 更新 RuntimeSnapshot
  -> ObservationEmitter 检查 failure_observations
  -> CompletionChecker 检查 completion_conditions
  -> 生成新事件并写回 EventQueue
```

单线程不代表场景不能并行，而是用确定性事件队列模拟多设备并发。

---

## 8. 策略算法库

### 8.1 `shared_pool_claim`

解决多机器人抢同一物料问题。

输入：

- `robot_id`
- `source_pool`
- `RuntimeSnapshot.workpiece_pool`
- `RuntimeSnapshot.material_claims`

逻辑：

```text
1. 检查 robot 是否 idle。
2. 检查 source_pool 是否存在未 claim 物料。
3. 按确定性顺序选择一个 material。
4. 原子写入 material_claims[material_id] = robot_id。
5. 返回 material_id / source_slot。
```

输出事件：

```text
global.workpiece_claimed
```

### 8.2 `backpressure`

解决下游传送带容量限制问题。

输入：

- `conveyor_id`
- `current_load`
- `max_capacity`
- `resume_threshold`

逻辑：

```text
if current_load >= max_capacity and blocked == false:
  set blocked = true
  emit conveyor.blocked

if current_load <= resume_threshold and blocked == true:
  set blocked = false
  emit conveyor.capacity_available
```

### 8.3 `queue_wait`

解决传送带断点或下游入口不可用时的等待问题。

输入：

- `conveyor_id`
- `material_id`
- `point_id`
- stop point occupancy
- downstream availability

逻辑：

```text
if next_stop_point_occupied or downstream_unavailable:
  enqueue material / action
  set device state = waiting_downstream
else:
  continue transport
```

### 8.4 `nearest_available_stop_point`

解决传送带断点选择问题。

输入：

- `conveyor_id`
- `material_id`
- stop point list
- occupancy map

逻辑：

```text
from current position towards exit:
  find nearest available stop point
if found:
  return point_id
else:
  fallback wait_at_nearest_upstream_stop_point
```

### 8.5 `downstream_release`

解决上下游传送带交接问题。

输入：

- upstream conveyor
- downstream conveyor
- upstream exit stop point
- downstream entry availability

逻辑：

```text
if downstream_entry_available and upstream_exit_stop_point_occupied:
  release material to downstream
  emit conveyor.stop_point_released
else:
  keep waiting / queue_wait
```

### 8.6 `resource_lock`

解决设备资源互斥。

输入：

- resource id
- action id
- lock owner

逻辑：

```text
if resource is unlocked:
  lock resource by action_id
  allow action
else:
  wait / retry / emit resource_conflict
```

### 8.7 `deadlock_detection`

解决无可执行行为但任务未完成的问题。

条件：

```text
no_enabled_behavior
and active_actions.empty == true
and completion_conditions_not_met
and event_queue.empty == true
```

输出：

```text
observation.deadlock_detected
```

---

## 9. 场景级调度算法

Scheduler 的核心流程：

```text
1. 事件唤醒
   根据 event_id 找到候选 behavior_rules。

2. Guard 过滤
   检查设备状态、资源状态、物料状态、容量状态。

3. Policy 决策
   执行 claim、backpressure、queue、stop point、resource lock 等策略。

4. Conflict resolution
   如果多个 action 竞争同一资源，按策略选择一个，其余等待。

5. Deterministic priority
   多个候选 action 同时可执行时，按固定优先级或 rule_id 排序。

6. Action dispatch
   把被选中的 action 交给 ActionExecutor。

7. Observation check
   无可执行行为但任务未完成时，触发异常观测。
```

---

## 10. 连续过程如何离散化

Runtime 不需要把连续行为建模成连续事件流，而是推进状态并在跨越边界时生成离散事件。

例如传送带负载：

```text
current_load: 4 -> 5
max_capacity: 5
blocked: false
  -> emit conveyor.blocked
  -> set blocked = true
```

如果后续 `current_load` 仍然是 5，不重复发 blocked。

恢复时：

```text
current_load: 4 -> 3
resume_threshold: 3
blocked: true
  -> emit conveyor.capacity_available
  -> set blocked = false
```

断点占用也是类似：

```text
material reaches stop_point_A
occupancy[A] was empty
  -> set occupancy[A] = material_id
  -> emit conveyor.stop_point_occupied
```

```text
material leaves stop_point_A
occupancy[A] == material_id
  -> set occupancy[A] = null
  -> emit conveyor.stop_point_released
```

---

## 11. 与 SimPy / DES 的关系

DES 是仿真范式，不是单一算法。

SimPy 是 Python 离散事件仿真工具包，不是调度算法本身。

本项目可以参考 SimPy 的：

- 事件队列。
- 仿真时钟。
- process / event / timeout。
- resource / store / container。

但以下部分需要本项目自己实现：

- `SceneBehaviorGraph` 规则解释。
- `event_bus` 路由和 topic 展开。
- `guard` 表达式求值。
- `policy_id -> policy algorithm` 映射。
- `RuntimeSnapshot` 状态一致性更新。
- 场景级资源仲裁和异常检测。

一句话：

> SimPy 可作为 Runtime 基础设施参考；真正的场景调度算法和策略算法由本系统围绕 `SceneBehaviorGraph` 自己实现。

---

## 12. 后续开发优先级

| 优先级 | 模块 | 目标 |
|---|---|---|
| P0 | `RuntimeSnapshot` 数据结构 | 明确运行时状态字段和初始化逻辑。 |
| P0 | `SignalBusRuntime` | 实现事件注册校验、route 投递、topic/subscription 展开。 |
| P0 | `RuleMatcher + GuardEvaluator` | 根据事件找到候选规则并过滤不可执行规则。 |
| P0 | `PolicyExecutor` | 实现 `shared_pool_claim`、`resource_lock`、`queue_wait`、`backpressure`。 |
| P1 | `ActionExecutor` | 启动和推进设备行为。 |
| P1 | `EffectApplier` | 解释并应用 `state_transition_rules.effects`。 |
| P1 | `CompletionChecker` | 判断仿真完成条件。 |
| P1 | `ObservationEmitter` | 输出死锁、超载、资源冲突等 observation。 |
| P2 | SimPy adapter | 如需要，可将事件队列/资源抽象接入 SimPy。 |
| P2 | Runtime trace viewer | 可视化事件流、规则命中、资源锁和状态变化。 |

---

## 13. 一句话总结

Runtime Scheduler 是后续需要独立开发的在线调度执行系统。它消费 Agent 生成的 `SceneBehaviorGraph`，维护 `RuntimeSnapshot`，并通过事件队列、规则匹配、策略算法、资源仲裁、行为执行和状态更新来驱动整个仿真运行。
