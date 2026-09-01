# Scene 09：旋转台定位与机械臂下料 Graph Explanation

## 场景整体

场景包含物料来源、旋转台、机械臂和工作台。人工搬运步骤第一阶段不建模为独立 actor，而是简化为旋转台 station_a 生成或接收工件。旋转台检测 station_a 有工件后，执行 90 度离散旋转，把工件转到机械臂可达的 station_b。旋转到位后，空闲机械臂抓取工件并放到工作台固定位置。工件到达工作台后离开系统或标记为完成。旋转台工位占用、旋转资源、机械臂资源和工作台占用必须互斥。

## 工艺模块

| 模块 | 模式 | 参与设备 | 启动事件 |
|---|---|---|---|
| `rotary_material_feed` | periodic | `source_station_1`, `rotary_table_1` | runtime.sim_start |
| `rotary_indexing` | cyclic | `rotary_table_1` | rotary_table.occupied |
| `robot_unload_to_workstation` | cyclic | `robot_1`, `workstation_1` | rotary_table.at_pick_station |

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
source_station_1/manual feed -> rotary_table_1.station_a -> rotate 90 deg -> rotary_table_1.station_b -> robot_1 -> workstation_1 -> complete
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
| `rotary_station_mutex` | `resource_lock`：支撑该场景动态调度。 |
| `workstation_mutex` | `resource_lock`：支撑该场景动态调度。 |

## 完成条件

- requested parts completed
- rotary_station_occupancy all empty
- workstation_buffer.workstation_1.occupied_by == null
- active_actions.empty == true
