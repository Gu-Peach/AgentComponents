# Scene 01 Graph Explanation

## 场景整体

这个场景模拟一条托盘分拣线：托盘先经过两段主传送带到达分拣位，随后两台机械臂从托盘上的 12 个工件中并行取料，并把工件放到上下两条出料传送带。出料传送带如果满载或没有可用停留点，会通过 backpressure 暂停相关机械臂继续抓取。

## 工艺模块

| 模块 | 作用 | 参与设备 |
|---|---|---|
| `pallet_transport` | 将托盘按停留点从第一段主传送带送到第二段主传送带，再送到分拣位。 | `main_conveyor_1`、`main_conveyor_2` |
| `parallel_robot_sorting` | 两台机械臂从同一个工件池 claim 工件并执行分拣。 | `robot_1`、`robot_2` |
| `output_conveying` | 出料传送带接收工件、按停留点推进、处理容量阻塞和恢复。 | `upper_out_conveyor_1`、`lower_out_conveyor_1` |

## 事件链路

```text
runtime.sim_start
  -> start_pallet_transport
  -> main_conveyor_1.transport_to_exit
  -> main_conveyor_1.pallet_ready
  -> transfer_pallet_main_conveyor_1_to_main_conveyor_2
  -> main_conveyor_2.transport_to_exit
  -> main_conveyor_2.pallet_ready
  -> robot_pick_request topic
  -> robot.pick_request
  -> global.workpiece_claimed
  -> robot.pick_done
  -> output_conveyor.material_arrived
```

传送带运行过程中，Runtime 会持续产生 `conveyor.stop_point_occupied` 和 `conveyor.stop_point_released`。这些事件负责驱动物料向下一个停留点推进、在前方占用时等待、以及在释放后恢复队列。

## 信号与 backpressure

当某条出料传送带 `current_load >= max_capacity`，或者没有可用停留点时，Runtime 发出：

```text
conveyor.blocked { conveyor_id, current_load, max_capacity, reason }
```

`event_bus` 将该事件投递到 `backpressure` topic，再唤醒 `blocked_conveyor_pauses_robot` 规则。规则通过 `backpressure` policy 找到受影响机械臂，并发出 `robot.pause_pick`。机械臂收到后不再启动新的 `pick_and_place`。

当停留点释放且负载低于恢复阈值时，Runtime 发出：

```text
conveyor.capacity_available { conveyor_id, current_load, resume_threshold }
```

`capacity_available_resumes_robot` 规则随后发出 `robot.resume_pick`，机械臂恢复参与共享工件池 claim。

## 关键状态

| 状态 | 作用 |
|---|---|
| `workpiece_pool` | 保存托盘上待 claim、已 claim、已完成的工件集合。 |
| `material_claims` | 记录某个工件被哪台机械臂 claim，避免重复抓取。 |
| `device_states` | 记录设备当前是 `idle`、`moving`、`busy`、`waiting_downstream` 等状态。 |
| `conveyor_stop_points` | 保存每条传送带由 entry / exit 插值得到的停留点。 |
| `conveyor_occupancy` | 保存每个停留点当前被哪个物料或托盘占用。 |
| `conveyor_queues` | 保存前方占用或下游不可接收时的等待队列。 |
| `conveyor_loads` | 保存每条传送带当前负载、容量上限、恢复阈值和 blocked 状态。 |
| `resource_locks` | 保存机械臂、夹爪、传送带表面等互斥资源占用。 |

## 策略

| 策略 | 解决的问题 |
|---|---|
| `shared_pool_claim` | 两台机械臂并行抢占工件时，保证同一工件只被 claim 一次。 |
| `nearest_available_stop_point` | 新物料进入传送带时选择合适停留点。 |
| `queue_wait` | 前方停留点或下游不可接收时让物料等待。 |
| `capacity_threshold` | 判断传送带是否 blocked，以及是否可以恢复。 |
| `downstream_release` | 判断出口停留点何时可以向下游释放。 |
| `resource_lock` | 防止机械臂、夹爪或传送带资源被多个动作同时占用。 |
| `deadlock_detection` | 当没有可执行动作且目标未完成时发出异常观测。 |

## 完成条件

仿真只有在以下条件同时满足时才结束：托盘上的 12 个工件全部完成分拣，所有 active action 结束，所有出料传送带负载为 0，所有传送带停留点为空，所有机械臂和传送带回到可收尾状态。
