# 托盘分拣线 demo：event_bus 说明

本文说明 `full_chain_schema.json` 中 `scene_behavior_graph.event_bus` 的事件注册、topic 订阅和事件路由。

该场景的核心链路是：两段主传送带按停留点占用把托盘依次送到分拣位，触发两台机械臂并行从托盘共享工件池 claim 物料；机械臂抓取完成后把物料送到出料传送带；出料传送带根据停留点占用和负载发出 backpressure 信号，控制机械臂暂停或恢复；全部物料完成后触发场景结束检查。

---

## 1. event_bus 在本案例中的作用

`event_bus` 不是 Runtime 的独立服务，而是 `SceneBehaviorGraph` 中的事件/信号建模结果。

运行时由 `SignalBusRuntime` 读取这些定义：

1. 校验某个事件是否已注册在 `events` 中。
2. 根据事件的 `payload_schema` 校验事件参数。
3. 查找 `routes` 中以该事件为 `from` 的路由。
4. 如果目标是 `rule`，直接唤醒对应 `behavior_rule`。
5. 如果目标是 `topic`，根据 `subscriptions[topic_id]` 展开成多个消费者消息。
6. 如果目标是 `runtime`，交给 Runtime 内部模块处理。

---

## 2. 已注册事件

| 事件 ID | kind | 由谁产生 | payload | 解决的问题 |
|---|---|---|---|---|
| `runtime.sim_start` | `global_event` | Runtime 初始化后产生 | 无 | 启动整条仿真链路，唤醒主传送带运输规则。 |
| `conveyor.stop_point_occupied` | `device_signal` | 传送带接收物料或推进到下一停留点时产生 | `conveyor_id`、`point_id`、`material_id` | 表示某个停留点被占用，用于触发继续推进或等待判断。 |
| `conveyor.stop_point_released` | `device_signal` | 物料离开某个停留点时产生 | `conveyor_id`、`point_id`、`material_id` | 表示某个停留点释放，用于恢复队列或容量判断。 |
| `main_conveyor_1.pallet_ready` | `device_signal` | 第一段主传送带完成托盘运输后产生 | `carrier_id`、`location`、`next_conveyor_id` | 表示托盘到达第一段出口，可尝试交给第二段主传送带。 |
| `main_conveyor_2.pallet_ready` | `device_signal` | 第二段主传送带完成托盘运输后产生 | `carrier_id`、`location` | 表示托盘已经到达可分拣位置，后续可以启动机械臂分拣。 |
| `robot.pick_request` | `global_event` | `robot_pick_request` topic 展开后产生 | `robot_id` | 给某个候选机械臂生成一次“尝试取料”的调度请求。 |
| `global.workpiece_claimed` | `global_event` | `claim_workpiece` 策略成功后产生 | `robot_id`、`material_id`、`source_slot` | 表示某个物料已经被某台机械臂原子 claim，避免两个机械臂抓同一物料。 |
| `robot.pick_done` | `device_signal` | 机械臂 `pick_and_place` 行为完成后产生 | `robot_id`、`material_id`、`target_conveyor` | 表示机械臂已把物料放到某条目标出料传送带。 |
| `output_conveyor.material_arrived` | `device_signal` | 物料到达出料传送带时产生 | `conveyor_id`、`material_id` | 告诉目标出料传送带启动或保持持续运输，并更新负载。 |
| `conveyor.blocked` | `device_signal` | 出料传送带无可用停留点、负载达到上限或下游不可接收时产生 | `conveyor_id`、`current_load`、`max_capacity`、`reason` | 表示传送带暂时无法继续接收物料，需要触发 backpressure 暂停机械臂后续抓取。 |
| `conveyor.capacity_available` | `device_signal` | 出料传送带负载降到恢复阈值时产生 | `conveyor_id`、`current_load`、`resume_threshold` | 表示传送带恢复接收能力，可以解除对应机械臂暂停。 |
| `robot.pause_pick` | `control_event` | backpressure 规则产生 | `robot_id`、`reason` | 控制指定机械臂暂停后续 pick 请求，不一定中断已经安全执行中的动作。 |
| `robot.resume_pick` | `control_event` | capacity available 规则产生 | `robot_id` | 控制指定机械臂恢复接收后续 pick 请求。 |
| `global.sorting_done` | `global_event` | 完成条件满足后产生 | `scene_id` | 通知 Runtime 执行完成检查、收尾和报告输出。 |

---

## 3. 已注册 topic

### `robot_pick_request`

`robot_pick_request` 是“机器人取料请求”广播主题。

它不是事件，也不是规则。它的作用是把 `main_conveyor_2.pallet_ready` 这种单个场景事件，展开成面向多台候选机械臂的 `robot.pick_request` 消息。

订阅关系：

| 订阅者 | message_event_id | filter | payload_template | 含义 |
|---|---|---|---|---|
| `idle_robot_requests_workpiece` | `robot.pick_request` | `device_states.robot_1 == idle` | `{ "robot_id": "robot_1" }` | 如果 `robot_1` 空闲，则给同一条取料规则投递一次 `robot_1` 的取料请求。 |
| `idle_robot_requests_workpiece` | `robot.pick_request` | `device_states.robot_2 == idle` | `{ "robot_id": "robot_2" }` | 如果 `robot_2` 空闲，则给同一条取料规则投递一次 `robot_2` 的取料请求。 |

这意味着 `robot_pick_request` topic 广播后，Scheduler 可能看到两条候选消息：

```json
{ "event_id": "robot.pick_request", "payload": { "robot_id": "robot_1" } }
{ "event_id": "robot.pick_request", "payload": { "robot_id": "robot_2" } }
```

最终哪个机械臂成功拿到物料，不由 topic 决定，而由 `idle_robot_requests_workpiece` 规则中的 `guard` 和 `claim_workpiece` policy 决定。

### `backpressure`

`backpressure` 是“出料传送带容量反馈”广播主题。

它把出料传送带的容量状态变化分发给暂停/恢复机械臂的规则。

订阅关系：

| 订阅者 | message_event_id | filter | payload_template | 含义 |
|---|---|---|---|---|
| `blocked_conveyor_pauses_robot` | `conveyor.blocked` | `event.event_id == conveyor.blocked` | `source_event.payload` | 当某条出料传送带 blocked，唤醒暂停机械臂规则。 |
| `capacity_available_resumes_robot` | `conveyor.capacity_available` | `event.event_id == conveyor.capacity_available` | `source_event.payload` | 当某条出料传送带容量恢复，唤醒恢复机械臂规则。 |

---

## 4. 事件路由说明

| route_id | from | to | delivery | 传递参数 | 处理的问题 |
|---|---|---|---|---|---|
| `route_sim_start_to_start_pallet_transport_rule` | `runtime.sim_start` | rule `start_pallet_transport` | `direct` | 无 | 仿真开始时直接唤醒主传送带运输规则。 |
| `route_main_conveyor_1_ready_to_main_conveyor_2_transport_rule` | `main_conveyor_1.pallet_ready` | rule `transfer_pallet_main_conveyor_1_to_main_conveyor_2` | `direct` | `carrier_id`、`location`、`next_conveyor_id` | 第一段主传送带到位后，检查第二段入口停留点并启动第二段运输。 |
| `route_pallet_ready_to_robot_pick_topic` | `main_conveyor_2.pallet_ready` | topic `robot_pick_request` | `broadcast` | `carrier_id`、`location`，并通过 subscription 补出 `robot_id` | 托盘到达分拣位后，不指定某一台机械臂，而是广播给所有候选机械臂。 |
| `route_workpiece_claimed_to_pick_rule` | `global.workpiece_claimed` | rule `claimed_workpiece_starts_pick` | `direct` | `robot_id`、`material_id`、`source_slot` | 工件 claim 成功后，启动对应机械臂的真实抓取/放置行为。 |
| `route_pick_done_to_material_arrival_rule` | `robot.pick_done` | rule `output_conveyor_runs_when_material_arrives` | `direct` | `robot_id`、`material_id`、`target_conveyor` | 机械臂放料完成后，通知目标出料传送带有物料到达，并启动或保持出料运输。 |
| `route_blocked_to_backpressure_topic` | `conveyor.blocked` | topic `backpressure` | `broadcast` | `conveyor_id`、`current_load`、`max_capacity`、`reason` | 出料传送带无可用停留点或达到最大承载时，把 blocked 信号广播给 backpressure 订阅规则。 |
| `route_capacity_available_to_backpressure_topic` | `conveyor.capacity_available` | topic `backpressure` | `broadcast` | `conveyor_id`、`current_load`、`resume_threshold` | 出料传送带负载恢复后，把 capacity available 信号广播给 backpressure 订阅规则。 |
| `route_sorting_done_to_completion_checker` | `global.sorting_done` | runtime `CompletionChecker` | `internal` | `scene_id` | 场景完成后交给 Runtime 内部完成检查、收尾和报告输出。 |

---

## 5. 关键路由展开示例

### 5.1 托盘通过两段主传送带到位

```text
runtime.sim_start
  -> route_sim_start_to_start_pallet_transport_rule
  -> behavior_rule start_pallet_transport
  -> action start_behavior main_conveyor_1.transport_to_exit
  -> conveyor.stop_point_occupied / conveyor.stop_point_released
  -> emit main_conveyor_1.pallet_ready
  -> route_main_conveyor_1_ready_to_main_conveyor_2_transport_rule
  -> behavior_rule transfer_pallet_main_conveyor_1_to_main_conveyor_2
  -> action start_behavior main_conveyor_2.transport_to_exit
  -> emit main_conveyor_2.pallet_ready
```

这里的重点是：传送带运输不是 entry 到 exit 的瞬移，而是 Runtime 根据 stop points 推进、等待和释放。

### 5.2 托盘到位后广播取料请求

```text
main_conveyor_2.pallet_ready
  -> route_pallet_ready_to_robot_pick_topic
  -> topic robot_pick_request
  -> subscriptions.robot_pick_request
  -> robot.pick_request { robot_id: robot_1 }
  -> robot.pick_request { robot_id: robot_2 }
  -> behavior_rule idle_robot_requests_workpiece
  -> guard 检查机械臂是否 idle、工件池是否非空、目标传送带是否未 blocked
  -> policy claim_workpiece 原子 claim 物料
  -> emit global.workpiece_claimed
```

这里的重点是：

- `robot_pick_request` 是广播主题，不直接执行动作。
- `robot.pick_request` 是真正投递给规则的事件。
- `idle_robot_requests_workpiece` 规则可能被同一个 topic 展开多次，但最终是否执行由 `guard + policy` 决定。

### 5.3 工件 claim 成功后启动机械臂行为

```text
global.workpiece_claimed { robot_id, material_id, source_slot }
  -> route_workpiece_claimed_to_pick_rule
  -> behavior_rule claimed_workpiece_starts_pick
  -> guard 检查 robot 仍然 idle、material_claims 与 robot 匹配、目标传送带未 blocked
  -> policy target_conveyor_selection 选择目标出料传送带
  -> action start_behavior robot.pick_and_place
```

这里的重点是：

- `global.workpiece_claimed` 是共享工件池的互斥结果。
- 它把“哪个机器人拿到了哪个物料”明确传给后续行为。
- 真正的设备行为是 `claimed_workpiece_starts_pick.action` 中的 `pick_and_place`。

### 5.4 出料传送带 backpressure

```text
conveyor.blocked { conveyor_id, current_load, max_capacity, reason }
  -> route_blocked_to_backpressure_topic
  -> topic backpressure
  -> subscriptions.backpressure
  -> behavior_rule blocked_conveyor_pauses_robot
  -> policy backpressure 解析 affected_robots
  -> emit robot.pause_pick { robot_id, reason, conveyor_id }
```

```text
conveyor.capacity_available { conveyor_id, current_load, resume_threshold }
  -> route_capacity_available_to_backpressure_topic
  -> topic backpressure
  -> subscriptions.backpressure
  -> behavior_rule capacity_available_resumes_robot
  -> policy backpressure 解析 affected_robots
  -> emit robot.resume_pick { robot_id, conveyor_id }
```

这里的重点是：

- blocked/capacity_available 是出料传送带的设备信号，触发原因来自停留点占用、容量阈值或下游接收状态。
- backpressure topic 负责把容量变化广播给暂停/恢复规则。
- 具体暂停哪些机械臂，由 `backpressure` policy 和 `backpressure_bindings` 决定。

---

## 6. 三类路由模式总结

| 路由模式 | 本案例例子 | 用途 |
|---|---|---|
| 事件 -> rule | `runtime.sim_start -> start_pallet_transport` | 明确的一对一行为触发。 |
| 事件 -> topic | `main_conveyor_2.pallet_ready -> robot_pick_request` | 一对多广播，再通过订阅展开成规则消息。 |
| 事件 -> runtime | `global.sorting_done -> CompletionChecker` | Runtime 内部检查、收尾、报告或异常观测。 |

当前基线优先使用这三类路径；`module` 和 `device` 目标类型保留为后续扩展，不作为托盘分拣 demo 的主链路。
