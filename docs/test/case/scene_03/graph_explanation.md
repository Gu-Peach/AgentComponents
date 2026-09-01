# Scene 03：双机械臂接力运输机构 Graph Explanation

## 场景整体

右侧物料上料台持续或按需生成工件，工件进入右侧传送带并按停留点移动到出口。当出口停留点有工件且第一台机械臂空闲时，robot_1 抓取工件并放到中间固定交接位。交接位被占用后，robot_2 在空闲且左侧传送带入口可接收时接走工件，并放入左侧传送带。左侧传送带继续按停留点运输到出口并释放。传送带默认只启用排队等待，也允许通过 capacity_threshold 扩展超载控制。

## 工艺模块

| 模块 | 模式 | 参与设备 | 启动事件 |
|---|---|---|---|
| `source_to_input_conveyor` | continuous | `source_station_1`, `right_in_conveyor_1` | runtime.sim_start |
| `robot_1_to_handoff` | cyclic | `robot_1` | input_conveyor.part_ready |
| `robot_2_to_output_conveyor` | cyclic | `robot_2`, `left_out_conveyor_1` | handoff_buffer.occupied |

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
source_station_1 -> right_in_conveyor_1 stop points -> robot_1 -> handoff_buffer_1 -> robot_2 -> left_out_conveyor_1 stop points -> exit
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
| `handoff_buffer_mutex` | `resource_lock`：支撑该场景动态调度。 |

## 完成条件

- source batch empty or requested output count reached
- handoff_buffers.handoff_buffer_1.occupied_by == null
- all conveyor_occupancy stop points are empty
- active_actions.empty == true
