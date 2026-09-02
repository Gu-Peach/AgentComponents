# Expected Answer: scene_03_case_03

## 1. 调度层面答案

### 1.1 期望模块 `modules`

| module_id | mode | devices | start_event | complete_event |
|---|---|---|---|---|
| `inbound_feed` | `continuous` | `source_station_1`, `right_in_conveyor_1` | `runtime.sim_start` | `right_in_conveyor_1.part_ready` |
| `two_robot_handoff` | `parallel_continuous` | `robot_1`, `robot_2` | `right_in_conveyor_1.part_ready` | `handoff_buffer_1.empty` |
| `outbound_transport` | `continuous` | `left_out_conveyor_1` | `robot_2.done` | `left_out_conveyor_1.material_released` |

### 1.2 期望事件 `event_bus.events`

| event_id | kind | 说明 |
|---|---|---|
| `runtime.sim_start` | `global_event` | 仿真开始事件 |
| `observation.deadlock_detected` | `observation` | 没有可执行行为且完成条件未满足 |
| `observation.invalid_requirement` | `observation` | 输入目标与场景事实或设备能力冲突 |
| `conveyor.material_arrived` | `device_signal` | 物料到达传送带入口或停留点 |
| `conveyor.stop_point_occupied` | `device_signal` | 物料占用某个传送带停留点 |
| `conveyor.stop_point_released` | `device_signal` | 物料释放某个传送带停留点 |
| `conveyor.blocked` | `device_signal` | 传送带因容量或下游不可接收进入阻塞 |
| `conveyor.capacity_available` | `device_signal` | 传送带释放容量后恢复可接收 |
| `robot.pick_request` | `control_event` | 请求空闲机械臂执行抓取或搬运动作 |
| `global.workpiece_claimed` | `global_event` | 共享物料或工位被某个执行单元成功 claim |
| `robot.pick_done` | `device_signal` | 机械臂抓取放置动作完成 |
| `source_station_1.material_ready` | `device_signal` | source_station_1.material_ready 场景事件 |
| `right_in_conveyor_1.part_ready` | `device_signal` | right_in_conveyor_1.part_ready 场景事件 |
| `handoff_buffer.occupied` | `device_signal` | handoff_buffer.occupied 场景事件 |
| `handoff_buffer.released` | `device_signal` | handoff_buffer.released 场景事件 |
| `robot_1.done` | `device_signal` | robot_1.done 场景事件 |

### 1.3 期望状态 `state_model`

| 状态变量 | 类型 | 作用 |
|---|---|---|
| `device_states` | 运行时状态 | 用于判定规则 guard、策略输入或完成条件。 |
| `signal_values` | 运行时状态 | 用于判定规则 guard、策略输入或完成条件。 |
| `resource_locks` | 运行时状态 | 用于判定规则 guard、策略输入或完成条件。 |
| `active_actions` | 运行时状态 | 用于判定规则 guard、策略输入或完成条件。 |
| `conveyor_stop_points` | 运行时状态 | 用于判定规则 guard、策略输入或完成条件。 |
| `conveyor_occupancy` | 运行时状态 | 用于判定规则 guard、策略输入或完成条件。 |
| `conveyor_queues` | 运行时状态 | 用于判定规则 guard、策略输入或完成条件。 |
| `conveyor_loads` | 运行时状态 | 用于判定规则 guard、策略输入或完成条件。 |
| `domain_state_variables` | 运行时状态 | 用于判定规则 guard、策略输入或完成条件。 |

### 1.4 期望行为规则 `behavior_rules`

| rule_id | module_id | trigger | action | 作用 |
|---|---|---|---|---|
| `accept_material_to_first_available_stop_point` | `two_robot_handoff` | `event` | `start_behavior` | 新物料进入传送带时写入入口侧最近可用停留点。 |
| `advance_material_to_next_stop_point` | `two_robot_handoff` | `event` | `start_behavior` | 前方停留点可用时，物料沿出口方向推进一个停留点。 |
| `wait_when_next_stop_point_occupied` | `two_robot_handoff` | `event` | `update_state` | 前方停留点或下游不可用时，将物料留在当前位置并进入等待队列。 |
| `release_material_when_downstream_available` | `two_robot_handoff` | `event` | `start_behavior` | 出口停留点有物料且下游可接收时释放物料。 |
| `emit_blocked_when_no_stop_point_available` | `two_robot_handoff` | `state_change` | `emit_event` | 无可用停留点或达到容量上限时发出阻塞观测。 |
| `emit_capacity_available_when_stop_point_released` | `two_robot_handoff` | `event` | `emit_event` | 停留点释放且负载低于恢复阈值时发出容量恢复事件。 |
| `source_feeds_right_conveyor` | `inbound_feed` | `event` | `start_behavior` | 右侧物料来源将工件送入输入传送带。 |
| `robot_1_moves_part_to_handoff` | `two_robot_handoff` | `event` | `start_behavior` | robot_1 将输入传送带出口工件搬到固定交接位。 |
| `robot_2_moves_handoff_to_output` | `two_robot_handoff` | `event` | `start_behavior` | robot_2 从交接位取料并放到左侧输出传送带。 |
| `prevent_duplicate_shared_resource_claim` | `two_robot_handoff` | `event` | `update_state` | 并行协作时防止两个执行单元 claim 同一个物料或缓存。 |

### 1.5 期望策略函数 `policies`

| policy_id | 策略类型 | 参数 |
|---|---|---|
| `deterministic_priority` | `deterministic_priority` | {"tie_breaker": "rule_id_then_instance_id"} |
| `resource_lock` | `resource_lock` | {"lock_scope": "instance_resource", "on_conflict": "wait"} |
| `deadlock_detection` | `deadlock_detection` | {"condition": "no_enabled_behavior and completion_conditions_not_met", "emit": "observation.deadlock_detected"} |
| `conveyor_queue_wait` | `queue_wait` | {"queue_scope": "conveyor_stop_points", "wait_when": "next_stop_point_occupied or downstream_unavailable", "resume_when": "stop_point_released or downstream_available"} |
| `conveyor_stop_point_selection` | `nearest_available_stop_point` | {"search_direction": "towards_exit", "fallback": "wait_at_nearest_upstream_stop_point"} |
| `backpressure` | `capacity_threshold` | {"blocked_when": "current_load >= max_capacity", "resume_when": "current_load <= resume_threshold", "pause_strategy": "pause_before_next_pick"} |
| `downstream_release` | `downstream_release` | {"release_when": "downstream_entry_available and exit_stop_point_occupied", "on_blocked": "queue_wait"} |
| `robot_resource_claim` | `shared_pool_claim` | {"mutual_exclusion": true, "claim_order": "deterministic_by_material_id", "eligible_when": "device_state == idle"} |
| `target_conveyor_selection` | `load_balancing` | {"candidates": ["right_in_conveyor_1", "left_out_conveyor_1"], "prefer": "lowest_current_load_not_blocked"} |

### 1.6 期望完成条件 `completion_conditions`

| condition_id | 条件表达 | 依赖状态 |
|---|---|---|
| completion_01 | `source batch empty or requested output count reached` | `state_model` / RuntimeSnapshot |
| completion_02 | `handoff_buffers.handoff_buffer_1.occupied_by == null` | `state_model` / RuntimeSnapshot |
| completion_03 | `all conveyor_occupancy stop points are empty` | `state_model` / RuntimeSnapshot |
| completion_04 | `active_actions.empty == true` | `state_model` / RuntimeSnapshot |

### 1.7 期望异常观测 `failure_observations`

| observation_id | 触发条件 | 期望说明 |
|---|---|---|
| `deadlock_detected` | `no_enabled_behavior and completion_conditions_not_met` | 必须进入观测或失败说明。 |
| `resource_conflict` | `resource lock conflict exceeds retry threshold` | 必须进入观测或失败说明。 |
| `invalid_requirement` | `goal references missing device, unsupported behavior, or impossible connection` | 必须进入观测或失败说明。 |

## 2. 规范层面答案

### 2.1 必填 section

最终 `SceneBehaviorGraph` 必须包含：

- `goal`
- `modules`
- `event_bus`
- `state_model`
- `behavior_rules`
- `state_transition_rules`
- `policies`
- `completion_conditions`
- `failure_observations`

### 2.2 字段结构要求

- `event_bus.events` 中每个事件必须包含 `event_id / kind / payload_schema / description`。
- `event_bus.routes` 中每条路由必须包含 `route_id / from / to / delivery`。
- `behavior_rules` 中每条规则必须包含 `rule_id / module_id / trigger / guard / policy / action`。
- `state_transition_rules` 中每条规则必须包含 `rule_id / trigger / effects`。
- `policies` 中每个策略必须包含 `type / params`。

### 2.3 引用关系完整性

- 所有 `instance_id` 必须来自 `SceneDocument.instances`，表达式型 `trigger.payload.*` 必须能从事件 payload 推导。
- 所有 `behavior_id` 必须来自对应设备 `DeviceSpec.transport_behaviors`。
- 所有 `trigger.event_id` 与 `routes[].from` 必须已在 `event_bus.events` 注册。
- 所有 `guard / policy / action / effects` 引用的状态变量必须存在于 `state_model`。

### 2.4 禁止项

最终图不得出现旧方案字段，也不得用旧规则简写替代 `trigger / guard / policy / action`。
