# Scene 05：圆桌双机械臂多出料分拣 Graph Explanation

## 场景整体

圆桌中心作为物料呈现区域，物料由人工上料过程简化为 Runtime 在圆桌固定位置生成。两台机械臂监控圆桌上的待处理物料，谁空闲谁 claim 一个物料，并根据出料传送带容量选择空闲或负载较低的目标传送带。目标传送带入口停留点可用时，机械臂执行 pick_and_place；如果某条传送带 blocked，则该传送带不参与目标选择。所有出料传送带都必须按停留点推进和释放。

## 工艺模块

| 模块 | 模式 | 参与设备 | 启动事件 |
|---|---|---|---|
| `round_table_material_supply` | periodic | `round_table_1` | runtime.sim_start |
| `dual_robot_table_dispatch` | parallel_continuous | `robot_1`, `robot_2` | round_table.material_available |
| `multi_output_conveying` | continuous | `out_conveyor_1`, `out_conveyor_2`, `out_conveyor_3`, `out_conveyor_4` | robot.pick_done |

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
round_table_1.station_a generated material -> robot_1 / robot_2 claim -> least-loaded available output conveyor -> exit
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
| `shared_table_workpiece_claim` | `shared_pool_claim`：支撑该场景动态调度。 |
| `target_conveyor_selection` | `load_balancing`：支撑该场景动态调度。 |

## 完成条件

- round_table_workpiece_pool empty after requested count
- all output conveyor stop points are empty
- active_actions.empty == true
