# RuntimeSnapshot 字段说明

本文用于解释 `3.RuntimeSnapshot/schema.json` 与 `example.json` 中每个板块和字段的含义。`RuntimeSnapshot` 是仿真运行时状态快照，用于记录当前信号值、设备状态、物料位置、传送带停留点占用、等待队列、资源锁和正在执行的动作。

## 1. schema 定位

`RuntimeSnapshot` 是运行时状态视图，通常存储在 Runtime memory / Redis 中。它不是长期事实库；关键事件摘要应通过事件日志或审计表落库，从而支持恢复和诊断。

```text
Runtime 执行 SceneBehaviorGraph
  + SignalBusRuntime 信号事件
  + Scheduler 资源调度
  -> RuntimeSnapshot
  -> Scheduler 下一轮调度 / 前端事件 / Runtime observation
```

## 2. `schema.json` 规范字段

| 字段 | 含义 |
| --- | --- |
| `schema_id` | 当前规范文件 ID。 |
| `schema_type` | 当前规范类型，示例为 `RuntimeSnapshotSchemaContract`。 |
| `version` | 规范版本。 |
| `name` | 规范名称。 |
| `description` | 规范用途说明。 |
| `source.kind` | 规范来源类型。 |
| `source.path` | 规范文件路径。 |
| `created_for` | 服务目标，即仿真运行时状态管理。 |
| `references` | 依赖的通用规范和 SceneBehaviorGraph 规范。 |
| `notes` | 存储边界说明。 |
| `required_sections` | 必须包含的一级字段。 |

## 3. 必填板块 `required_sections`

| 板块 | 含义 |
| --- | --- |
| `run_id` | 当前仿真运行 ID。 |
| `clock` | 仿真时钟。 |
| `signal_values` | 当前信号值集合。 |
| `device_fsm_states` | 设备 FSM 状态集合。 |
| `material_locations` | 物料位置集合。 |
| `conveyor_stop_points` | 传送带停留点定义或 Runtime 派生结果摘要。 |
| `conveyor_occupancy` | 传送带每个停留点当前被哪个物料占用。 |
| `conveyor_queues` | 传送带内部等待队列。 |
| `conveyor_loads` | 传送带当前负载、容量、恢复阈值和 blocked 状态。 |
| `wait_queues` | 等待队列集合。 |
| `resource_locks` | 资源锁集合。 |
| `active_actions` | 当前正在执行的动作集合。 |

## 4. 示例元信息

| 字段 | 含义 |
| --- | --- |
| `schema_id` | 示例快照 ID。 |
| `schema_type` | 示例类型，实际快照使用 `RuntimeSnapshot`。 |
| `source.kind` | 来源类型，`runtime_example` 表示运行时示例。 |
| `source.run_id` | 该快照所属 run。 |
| `references` | 快照引用的 SceneBehaviorGraph 或运行记录。 |
| `notes` | 存储和落库策略说明。 |

## 5. 运行 ID `run_id`

| 字段 | 含义 |
| --- | --- |
| `run_id` | 当前仿真运行 ID，用于关联 SceneBehaviorGraph、事件日志和前端订阅。 |

## 6. 仿真时钟 `clock`

| 字段 | 含义 |
| --- | --- |
| `clock` | 当前仿真时间或运行时钟，示例中单位按秒理解。 |

`clock` 可用于排序信号、计算超时、恢复动作进度和前端动画同步。

## 7. 信号值 `signal_values`

`signal_values` 保存当前关键运行信号值。

| Key 格式 | 含义 |
| --- | --- |
| `instance_id.signal_port` | 某设备实例上的某个信号端口值。 |

| 示例 Key | 含义 |
| --- | --- |
| `conveyor_1.part_ready` | 传送带物料到位信号。 |
| `robot_1.busy` | 机械臂是否忙碌。 |
| `robot_1.done` | 机械臂动作是否完成。 |

信号值可以是布尔值、事件状态、命令状态或后续扩展的 payload 引用。

## 8. 设备状态 `device_fsm_states`

`device_fsm_states` 保存每个设备实例当前 FSM 状态。

| Key 格式 | 含义 |
| --- | --- |
| `instance_id` | 设备实例 ID。 |
| value | 当前 FSM 状态，必须来自对应 `DeviceSpec.runtime_contract.fsm_states`。 |

## 9. 物料位置 `material_locations`

`material_locations` 保存物料实例当前所在位置。

| Key 格式 | 含义 |
| --- | --- |
| `material_id` | 物料实例 ID。 |
| value | 位置引用，可指向设备接口、载具槽位、库位或动作中间状态。 |

示例中 `part_001 -> conveyor_1.sp_04` 表示物料位于传送带第 4 个停留点，该点通常是出口停留点。

## 10. 传送带停留点 `conveyor_stop_points`

`conveyor_stop_points` 保存 Runtime 根据 `DeviceSpec.conveyor.type_specific_contract.stop_point_model` 和场景实例参数派生出的停留点摘要。它不是新的设备，也不是新的行为规则，只是运行时定位和占用判断需要的点位集合。

| 字段 | 含义 |
| --- | --- |
| `conveyor_id` | 传送带实例 ID。 |
| `generation` | 停留点生成方式，第一阶段通常为 `linear_interpolation`。 |
| `points` | 停留点列表。 |
| `point_id` | 停留点 ID，例如 `conveyor_1.sp_04`。 |
| `index` | 停留点顺序，越大越靠近出口。 |
| `t` | entry 到 exit 的插值比例，`0` 表示入口，`1` 表示出口。 |
| `role` | 点位角色，可为 `entry`、`middle`、`exit`。 |

## 11. 停留点占用 `conveyor_occupancy`

`conveyor_occupancy` 保存每个停留点当前被哪个物料或载具占用。Scheduler 用它判断物料是否可以继续前进，是否需要等待，是否需要发出 blocked。

| Key 格式 | 含义 |
| --- | --- |
| `conveyor_id.point_id` | 某条传送带上的某个停留点。 |
| value | 占用该停留点的 `material_id` 或 `carrier_id`；`null` 表示空闲。 |

## 12. 传送带队列 `conveyor_queues`

`conveyor_queues` 保存由于前方停留点占用、出口不可释放或下游设备忙碌而产生的等待队列。

| 字段 | 含义 |
| --- | --- |
| `queue_id` | 传送带停留点队列 ID。 |
| `waiting_materials` | 当前等待推进或释放的物料列表。 |

## 13. 传送带负载 `conveyor_loads`

`conveyor_loads` 保存传送带容量状态，配合 `conveyor_occupancy` 判断是否进入 backpressure。

| 字段 | 含义 |
| --- | --- |
| `current_load` | 当前传送带上承载的物料或载具数量。 |
| `max_capacity` | 当前实例最大容量，来自 SceneDocument 参数覆盖或 DeviceSpec 默认值。 |
| `resume_threshold` | 从 blocked 恢复接收的阈值。 |
| `blocked` | 当前是否处于阻塞状态。 |

## 14. 等待队列 `wait_queues`

`wait_queues` 保存运行时等待关系，通常由 `SceneBehaviorGraph.event_bus`、策略规则和设备状态共同维护。

| Key 格式 | 含义 |
| --- | --- |
| `instance_id.queue_id` | 某设备实例的等待队列。 |
| value | 队列中的物料、动作或事件 ID 列表。 |

示例中 `conveyor_1.stop_point_queue: []` 表示传送带停留点队列当前没有等待物料。

## 15. 资源锁 `resource_locks`

`resource_locks` 保存调度资源是否被占用。

| Key 格式 | 含义 |
| --- | --- |
| `instance_id.resource_id` | 某设备实例上的某个调度资源。 |
| value | 占用该资源的动作 ID；`null` 表示未占用。 |

示例中 `robot_1.gripper: null` 表示机械臂夹爪当前可用。

## 16. 活动动作 `active_actions`

`active_actions` 保存当前正在执行的动作集合。

| 字段 | 含义 |
| --- | --- |
| `active_actions` | 动作 ID 到执行状态的映射。空对象表示当前没有正在执行的动作。 |

后续可扩展保存动作开始时间、预计完成时间、进度、占用资源和取消状态。

## 17. 下游使用方式

```text
Scheduler 读取 RuntimeSnapshot
  -> 判断某个设备 enabled / waiting / blocked / executing

ObservationEmitter 读取 RuntimeSnapshot
  -> 判断 deadlock / overload / resource_conflict 等异常观测

前端读取 RuntimeSnapshot 或事件流
  -> 展示设备状态、物料位置、等待队列和动画进度
```
