# Scene 08：物料与托盘同步到位装载

## 测试目的

验证 Agent 能否把场景 8 建模为可执行、可校验的 `SceneBehaviorGraph`，并正确处理该场景中的关键调度约束。

## 场景来源

- 图片：`docs/business/test/8.png`
- case：`docs/test/case/scene_08`
- 设备规范：`docs/business/SimulationSchema/1.DeviceSpec/`

## 用户目标摘要

物料侧出料台和传送带持续送料，托盘侧传送带同步运输空托盘；当物料和托盘都到位时，机械臂把物料装到托盘，达到数量后托盘输出。

## 设备与对象

| 类型 | 实例 | spec_id | 作用 |
|---|---|---|---|
| `material_source_station` | `part_source_1` | `material_source_station_1` | 物料出料台 |
| `conveyor` | `part_conveyor_1` | `conveyor_1` | 物料侧传送带 |
| `conveyor` | `pallet_conveyor_1` | `conveyor_1` | 托盘侧传送带 |
| `robot_arm` | `robot_1` | `robot_arm_1` | 装托盘机械臂 |
| `workpiece_carrier` | `pallet_1` | `carrier_tray_1` | 待装载托盘 |

## 主要调度难点

- 物料到位和托盘到位必须同时满足才能抓取。
- 托盘目标装载数达到后才可输出。
- 两个传送带都必须按停留点排队等待。

## 预期验证重点

- Agent 最终产物必须是 `SceneBehaviorGraph`。
- 行为规则必须使用 `trigger / guard / policy / action`。
- 事件必须先在 `event_bus.events` 注册，再被 route、rule 或 transition 引用。
- 涉及传送带时，必须建模 `conveyor_stop_points`、`conveyor_occupancy`、`conveyor_queues` 和 `conveyor_loads`。
