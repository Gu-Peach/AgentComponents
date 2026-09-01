# Scene 06：仓储柜双升降台入库出库

## 测试目的

验证 Agent 能否把场景 6 建模为可执行、可校验的 `SceneBehaviorGraph`，并正确处理该场景中的关键调度约束。

## 场景来源

- 图片：`docs/business/test/6.png`
- case：`docs/test/case/scene_06`
- 设备规范：`docs/business/SimulationSchema/1.DeviceSpec/`

## 用户目标摘要

出料口间隔出物料，经入口传送带到第一升降台，升降台把物料放入空闲库位；第二升降台从库位取料并送到末端传送带输出。

## 设备与对象

| 类型 | 实例 | spec_id | 作用 |
|---|---|---|---|
| `material_source_station` | `source_station_1` | `material_source_station_1` | 入口物料来源 |
| `conveyor` | `inbound_conveyor_1` | `conveyor_1` | 入库入口传送带 |
| `lift_table` | `inbound_lift_1` | `lift_table_1` | 入库升降台 |
| `storage_rack` | `storage_rack_1` | `storage_rack_1` | 仓储柜 / 货架 |
| `lift_table` | `outbound_lift_1` | `lift_table_1` | 出库升降台 |
| `conveyor` | `outbound_conveyor_1` | `conveyor_1` | 末端出库传送带 |

## 主要调度难点

- 入口升降台一次只能搬运一个物料。
- 库位必须先 reserve 再 store。
- 入口传送带在升降台忙时按停留点排队。
- 末端传送带出口释放后物料消失。

## 预期验证重点

- Agent 最终产物必须是 `SceneBehaviorGraph`。
- 行为规则必须使用 `trigger / guard / policy / action`。
- 事件必须先在 `event_bus.events` 注册，再被 route、rule 或 transition 引用。
- 涉及传送带时，必须建模 `conveyor_stop_points`、`conveyor_occupancy`、`conveyor_queues` 和 `conveyor_loads`。
