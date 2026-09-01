# 3. RuntimeSnapshot

> 当前主链路请参考 `../README.md`、`../device_data_structure.md` 和 `../4.SceneBehaviorGraph/`。

`RuntimeSnapshot` 是仿真运行时状态快照，主要存储在 Redis / Runtime memory，关键事件摘要落 Postgres。

它不定义行为规则，也不定义传送带停留点如何生成；这些规则来自 `DeviceSpec` 和 `SceneBehaviorGraph`。`RuntimeSnapshot` 只记录当前每个设备、物料、信号、停留点、队列和资源锁的事实状态。

## 职责

- 保存当前信号值、设备 FSM、物料位置、传送带停留点占用、等待队列、资源锁和活动动作。
- 支撑 Runtime 调度、恢复、诊断和前端实时展示。
- 为 `Scheduler`、`SignalBusRuntime`、`SnapshotManager` 提供实时状态事实。

## 输入与输出

| 项目 | 内容 |
|---|---|
| 上游输入 | Runtime 执行动作、SignalBus 事件、Scheduler 状态变化。 |
| 输出 | 当前运行状态快照。 |
| 下游消费者 | Scheduler、SignalBusRuntime、SnapshotManager、ObservationEmitter、前端事件流。 |

## Key 含义

### 通用元信息

| Key | 含义 |
|---|---|
| `schema_id` | 当前运行时快照示例的唯一标识。 |
| `schema_type` | JSON 类型；示例使用 `RuntimeSnapshot`。 |
| `version` | 规范版本。 |
| `name` | 快照名称。 |
| `description` | 快照用途说明。 |
| `source` | 快照来源，通常是 Runtime run。 |
| `created_for` | 该快照服务的运行、恢复或诊断目标。 |
| `references` | 引用的 SceneBehaviorGraph、场景或运行记录。 |
| `notes` | 存储边界和恢复策略说明。 |

### 运行时状态字段

| Key | 含义 |
|---|---|
| `run_id` | 当前仿真运行 ID。 |
| `clock` | 仿真时钟或运行时间戳。 |
| `signal_values` | 当前所有关键信号值。 |
| `device_fsm_states` | 各设备实例当前 FSM 状态。 |
| `material_locations` | 各物料当前所在位置。 |
| `conveyor_stop_points` | 传送带停留点定义或派生结果摘要。 |
| `conveyor_occupancy` | 每个传送带停留点当前被哪个物料或载具占用。 |
| `conveyor_queues` | 传送带内部等待队列。 |
| `conveyor_loads` | 传送带当前负载、容量、恢复阈值和 blocked 状态。 |
| `wait_queues` | 等待队列状态，例如出口等待物料列表。 |
| `resource_locks` | 资源锁状态，记录资源是否被设备或动作占用。 |
| `active_actions` | 当前正在执行的动作。 |

### 常见值语义

| Key | 含义 |
|---|---|
| `conveyor_1.part_ready` | 某设备实例的具体信号值，格式通常为 `instance_id.signal_port`。 |
| `robot_1.gripper` | 某设备实例的具体资源锁，格式通常为 `instance_id.resource_id`。 |
| `part_001` | 物料实例 ID。 |
| `conveyor_1.sp_04` | 传送带停留点位置，通常由 Runtime 根据 entry/exit 插值得到。 |

### 规范辅助字段

| Key | 含义 |
|---|---|
| `required_sections` | `RuntimeSnapshot` 必须包含的一级字段列表。 |
| `kind` | 来源类别，例如 `runtime_example`、`manual_design`。 |
| `path` | 当前规范或示例文件路径。 |

### 示例状态 Key

| Key | 含义 |
|---|---|
| `conveyor_1` | 示例中的传送带设备实例状态。 |
| `robot_1` | 示例中的机械臂设备实例状态。 |
| `robot_1.busy` | 机械臂 busy 信号当前值。 |
| `robot_1.done` | 机械臂 done 信号当前值。 |
| `conveyor_1.stop_point_queue` | 传送带停留点等待队列。 |
| `null` | 表示资源当前未被占用或当前无执行行为。 |
