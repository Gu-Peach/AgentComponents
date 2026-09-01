# Scene 04：传送带中段机械臂加工模拟 Graph Explanation

## 场景整体

物料由传送带起点的上料台生成并进入主传送带，主传送带按停留点推进。工件到达中间加工停留点后，传送带暂停该工件的继续前进，空闲机械臂移动到固定加工位置执行一次模拟加工动作。加工完成后释放该停留点，物料继续沿传送带向出口移动并离开系统。若中间加工点被占用，后续物料停在上游停留点等待。

## 工艺模块

| 模块 | 模式 | 参与设备 | 启动事件 |
|---|---|---|---|
| `material_generation` | periodic | `source_station_1` | runtime.sim_start |
| `inline_stop_point_transport` | continuous | `main_conveyor_1` | source.material_available |
| `robot_processing_at_midpoint` | cyclic | `robot_1`, `robot_2` | workpiece.processing_position_ready |

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
source_station_1 -> main_conveyor_1 stop points -> processing_stop_point -> robot processing -> main_conveyor_1 exit
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
| `processing_station_mutex` | `resource_lock`：支撑该场景动态调度。 |
| `processing_robot_selection` | `deterministic_priority`：支撑该场景动态调度。 |

## 完成条件

- all requested materials processed == true
- all conveyor_occupancy stop points are empty
- active_actions.empty == true
