# Expected Answer: scene_09_case_01

## 1. 调度层面答案

### 1.1 期望模块 `modules`

| module_id | mode | devices | start_event | complete_event |
|---|---|---|---|---|
| `rotary_material_feed` | `continuous` | `source_station_1`, `rotary_table_1` | `runtime.sim_start` | `rotary_table.occupied` |
| `rotary_indexing` | `sequential` | `rotary_table_1` | `rotary_table.occupied` | `rotary_table.at_pick_station` |
| `robot_unload_to_workstation` | `sequential` | `robot_1`, `workstation_1` | `rotary_table.at_pick_station` | `global.process_done` |

### 1.2 期望事件 `event_bus.events`

| event_id | kind | 说明 |
|---|---|---|
| `runtime.sim_start` | `global_event` | 仿真开始事件 |
| `observation.deadlock_detected` | `observation` | 没有可执行行为且完成条件未满足 |
| `observation.invalid_requirement` | `observation` | 输入目标与场景事实或设备能力冲突 |
| `robot.pick_request` | `control_event` | 请求空闲机械臂执行抓取或搬运动作 |
| `global.workpiece_claimed` | `global_event` | 共享物料或工位被某个执行单元成功 claim |
| `robot.pick_done` | `device_signal` | 机械臂抓取放置动作完成 |
| `rotary_table.occupied` | `device_signal` | rotary_table.occupied 场景事件 |
| `rotary_table.rotate_request` | `device_signal` | rotary_table.rotate_request 场景事件 |
| `rotary_table.at_pick_station` | `device_signal` | rotary_table.at_pick_station 场景事件 |
| `robot_1.done` | `device_signal` | robot_1.done 场景事件 |
| `workstation.material_received` | `device_signal` | workstation.material_received 场景事件 |
| `global.process_done` | `global_event` | global.process_done 场景事件 |

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
| `feed_material_to_rotary_station` | `rotary_material_feed` | `event` | `start_behavior` | 将人工搬运简化为 station_a 生成/接收工件。 |
| `rotate_material_to_pick_station` | `rotary_indexing` | `event` | `start_behavior` | station_a 有工件后旋转 90 度到机械臂可达 station_b。 |
| `robot_moves_rotary_part_to_workstation` | `robot_unload_to_workstation` | `event` | `start_behavior` | 旋转到位后机械臂将工件搬到工作台并完成。 |

### 1.5 期望策略函数 `policies`

| policy_id | 策略类型 | 参数 |
|---|---|---|
| `deterministic_priority` | `deterministic_priority` | {"tie_breaker": "rule_id_then_instance_id"} |
| `resource_lock` | `resource_lock` | {"lock_scope": "instance_resource", "on_conflict": "wait"} |
| `deadlock_detection` | `deadlock_detection` | {"condition": "no_enabled_behavior and completion_conditions_not_met", "emit": "observation.deadlock_detected"} |
| `robot_resource_claim` | `shared_pool_claim` | {"mutual_exclusion": true, "claim_order": "deterministic_by_material_id", "eligible_when": "device_state == idle"} |
| `station_mutex` | `resource_lock` | {"lock_scope": "rotary_or_round_table_station", "on_conflict": "wait"} |

### 1.6 期望完成条件 `completion_conditions`

| condition_id | 条件表达 | 依赖状态 |
|---|---|---|
| completion_01 | `all requested parts completed at workstation` | `state_model` / RuntimeSnapshot |
| completion_02 | `rotary_station_occupancy.station_a == null` | `state_model` / RuntimeSnapshot |
| completion_03 | `rotary_station_occupancy.station_b == null` | `state_model` / RuntimeSnapshot |
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
