# Scene 02：多机械臂远端优先托盘分拣线 Graph Explanation

## 场景整体

场景从左到右包括托盘出料口、承载 12 个工件的托盘、长主传送带、三台机械臂，以及每台机械臂对应的一条出料传送带。出料口按节拍输出托盘，托盘进入主传送带后按停留点逐步前进。调度策略优先选择最远端空闲机械臂工位：如果 robot_3 空闲，托盘优先送到 robot_3；否则尝试 robot_2，再尝试 robot_1。当三台机械臂均忙时，主传送带保持当前停留点占用并停止继续放行，上游出料口暂停产生新托盘。机械臂从到位托盘中处理 12 个工件，并放入各自对应的出料传送带。每条出料传送带都按停留点容量处理 backpressure：满载或无停留点时发出 conveyor.blocked，容量恢复后发出 conveyor.capacity_available。空托盘沿主线继续到末端并离开系统。

## 工艺模块

| 模块 | 模式 | 参与设备 | 启动事件 |
|---|---|---|---|
| `pallet_generation` | periodic | `pallet_source_1` | runtime.sim_start |
| `farthest_idle_pallet_routing` | continuous | `main_conveyor_1` | pallet_source.pallet_ready |
| `three_robot_sorting` | parallel_continuous | `robot_1`, `robot_2`, `robot_3` | pallet.arrived_at_robot_station |
| `robot_output_conveying` | continuous | `robot_1_out_conveyor`, `robot_2_out_conveyor`, `robot_3_out_conveyor` | robot.pick_done |

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
pallet_source_1 -> main_conveyor_1 stop points -> farthest idle robot station -> robot-specific output conveyor -> empty pallet exits main line
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
| `farthest_idle_robot_assignment` | `deterministic_priority`：支撑该场景动态调度。 |
| `shared_pallet_workpiece_claim` | `shared_pool_claim`：支撑该场景动态调度。 |

## 完成条件

- all planned pallets processed or exited
- all pallet_workpiece_pools remaining_count == 0
- all conveyor_occupancy stop points are empty
- active_actions.empty == true
