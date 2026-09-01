# Scene 08：物料与托盘同步到位装载 Graph Explanation

## 场景整体

场景包含物料出料台、物料侧传送带、托盘、托盘侧传送带和一台机械臂。物料出料台持续输出工件，工件进入物料传送带并按停留点排队。空托盘进入托盘传送带并移动到装载位置。当物料传送带出口有工件且托盘位到达装载位置时，机械臂抓取工件并放入托盘空槽。装载过程中，后续物料和托盘必须停在各自传送带上游停留点等待。托盘达到目标装载数量后，托盘传送带继续将该托盘运输到出口并离开系统，后续空托盘补位。

## 工艺模块

| 模块 | 模式 | 参与设备 | 启动事件 |
|---|---|---|---|
| `part_feed` | continuous | `part_source_1`, `part_conveyor_1` | runtime.sim_start |
| `pallet_feed` | continuous | `pallet_conveyor_1` | runtime.sim_start |
| `synchronized_robot_loading` | cyclic | `robot_1`, `pallet_1` | loading.inputs_ready |
| `loaded_pallet_release` | one_shot_per_pallet | `pallet_conveyor_1` | pallet.load_complete |

## 关键事件链路

```text
runtime.sim_start
  -> 场景起始规则
  -> 设备行为执行
  -> event_bus 路由事件
  -> behavior_rules 根据 guard / policy 判断下一步
  -> RuntimeSnapshot 更新状态
  -> completion_conditions 判断是否结束
```

具体到本场景，核心流程是：

```text
part_source_1 -> part_conveyor_1 stop points + pallet_conveyor_1 stop points -> synchronized loading by robot_1 -> loaded pallet exits
```

## Runtime 需要维护的状态

- `device_states`：设备当前状态，例如 idle、moving、busy、blocked。
- `resource_locks`：机械臂、夹爪、传送带表面、升降平台、旋转台等互斥资源。
- `active_actions`：正在执行的设备行为。
- `material_locations`：物料或托盘当前所在位置。
- `conveyor_stop_points` / `conveyor_occupancy` / `conveyor_queues` / `conveyor_loads`：涉及传送带时用于描述停留点、占用、排队和容量。

## 策略

| 策略 | 作用 |
|---|---|
| `deterministic_priority` | `deterministic_priority`：按工艺阶段和设备优先级选择下一条可执行规则。 |
| `conveyor_queue_wait` | `queue_wait`：支撑该场景动态调度。 |
| `conveyor_stop_point_selection` | `nearest_available_stop_point`：支撑该场景动态调度。 |
| `backpressure` | `capacity_threshold`：支撑该场景动态调度。 |
| `downstream_release` | `downstream_release`：支撑该场景动态调度。 |
| `resource_lock` | `resource_lock`：支撑该场景动态调度。 |
| `deadlock_detection` | `deadlock_detection`：no_enabled_behavior and completion_conditions_not_met |
| `synchronized_arrival` | `synchronization`：支撑该场景动态调度。 |
| `pallet_slot_selection` | `deterministic_priority`：first_empty_slot |
| `batch_count_threshold` | `capacity_threshold`：支撑该场景动态调度。 |

## 完成条件

- carrier_loads.pallet_1.load_count == carrier_loads.pallet_1.target_count
- loaded pallet exits pallet_conveyor_1
- all conveyor_occupancy stop points are empty
- active_actions.empty == true
