# Scene 07：机床旁机械臂加工转运 Graph Explanation

## 场景整体

输入传送带起点持续生成或接收物料，物料按停留点推进到靠近机械臂的取料点。机械臂空闲时从输入传送带出口取料，移动到机床或固定加工位，等待加工完成后再把物料放到输出传送带入口。输出传送带按停留点推进并在出口释放物料。输入传送带出口、加工位和输出传送带入口都需要互斥，防止物料穿透或重复搬运。

## 工艺模块

| 模块 | 模式 | 参与设备 | 启动事件 |
|---|---|---|---|
| `input_feed` | continuous | `source_station_1`, `input_conveyor_1` | runtime.sim_start |
| `robot_machine_processing` | cyclic | `robot_1` | input_conveyor.part_ready |
| `output_transport` | continuous | `output_conveyor_1` | machine.process_done |

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
source_station_1 -> input_conveyor_1 stop points -> robot_1 -> machine_process_buffer -> robot_1 -> output_conveyor_1 stop points -> exit
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
| `machine_buffer_mutex` | `resource_lock`：支撑该场景动态调度。 |

## 完成条件

- requested parts processed == true
- machine_process_buffer_1.occupied_by == null
- all conveyor_occupancy stop points are empty
- active_actions.empty == true
