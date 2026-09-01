# Scene 06：仓储柜双升降台入库出库 Graph Explanation

## 场景整体

左侧出料口按节拍生成物料，物料进入入口传送带并按停留点前进到第一升降台。第一升降台空闲且仓储柜存在空库位时，接收物料、移动到对应高度并将物料存入库位。第一升降台工作时，入口传送带出口物料等待，后续物料依次停在上游停留点。第二升降台根据出库策略从仓储柜取出物料，移动到末端传送带对接高度并释放物料。末端传送带按停留点运输到出口后物料离开系统。

## 工艺模块

| 模块 | 模式 | 参与设备 | 启动事件 |
|---|---|---|---|
| `inbound_feed` | continuous | `source_station_1`, `inbound_conveyor_1` | runtime.sim_start |
| `store_with_lift` | cyclic | `inbound_lift_1`, `storage_rack_1` | inbound_conveyor.part_ready |
| `retrieve_with_lift` | cyclic | `storage_rack_1`, `outbound_lift_1` | storage.request_release |
| `outbound_transport` | continuous | `outbound_conveyor_1` | outbound_lift.material_released |

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
source_station_1 -> inbound_conveyor_1 stop points -> inbound_lift_1 -> storage_rack_1 cells -> outbound_lift_1 -> outbound_conveyor_1 stop points -> exit
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
| `storage_slot_selection` | `storage_slot_selection`：first_available |
| `storage_release_selection` | `storage_release_selection`：fifo |
| `lift_level_match` | `deterministic_priority`：支撑该场景动态调度。 |

## 完成条件

- requested inbound/outbound count completed
- all storage operations settled
- all conveyor_occupancy stop points are empty
- active_actions.empty == true
