# Scene 01：托盘分拣场景

## 测试目的

验证 Agent 能否把图 1 的托盘分拣任务建模为停留点感知的 `SceneBehaviorGraph`，并覆盖两段主传送带串联运输、两台机械臂共享工件池、两条出料传送带 backpressure 和容量恢复。

## 场景来源

- 图片：`docs/business/test/1.png`
- 场景事实：`docs/business/SimulationSchema/2.SceneDocument/example.json`
- 设备规范：`docs/business/SimulationSchema/1.DeviceSpec/`

## 设备与对象

| 类型 | 实例 | 作用 |
|---|---|---|
| `workpiece_carrier` | `pallet_1` | 承载 12 个待分拣工件。 |
| `conveyor` | `main_conveyor_1`、`main_conveyor_2` | 两段主传送带，负责把托盘送到分拣位。 |
| `robot_arm` | `robot_1`、`robot_2` | 从托盘共享工件池 claim 工件并放到目标出料传送带。 |
| `conveyor` | `upper_out_conveyor_1`、`lower_out_conveyor_1` | 出料传送带，负责接收分拣后的工件并处理停留点容量。 |
| `workpiece` | `part_001` - `part_012` | 待分拣工件。 |

## 验证重点

- 主传送带必须是 `main_conveyor_1 -> main_conveyor_2` 串联运输，不能直接从第一段完成后启动分拣。
- 所有传送带必须使用 `stop_point_buffered_transport`，并在 `state_model` 中声明停留点、占用、队列和容量状态。
- 两台机械臂必须通过共享工件池策略 claim 工件，避免同一工件被重复抓取。
- 出料传送带无可用停留点或容量满时必须发出 `conveyor.blocked`，容量恢复后发出 `conveyor.capacity_available`。
- Agent 最终产物只能是 `SceneBehaviorGraph`，不能生成旧方案中的 `SimPlan` 或其他中间 schema。
