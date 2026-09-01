# Scene 05：圆桌双机械臂多出料分拣

## 测试目的

验证 Agent 能否把场景 5 建模为可执行、可校验的 `SceneBehaviorGraph`，并正确处理该场景中的关键调度约束。

## 场景来源

- 图片：`docs/business/test/5.png`
- case：`docs/test/case/scene_05`
- 设备规范：`docs/business/SimulationSchema/1.DeviceSpec/`

## 用户目标摘要

圆桌固定位置生成物料，两台机械臂从圆桌取料并放到空闲出料传送带，多个出料传送带按停留点容量接收物料。

## 设备与对象

| 类型 | 实例 | spec_id | 作用 |
|---|---|---|---|
| `rotary_table` | `round_table_1` | `rotary_table_1` | 圆桌 / 物料呈现台 |
| `robot_arm` | `robot_1` | `robot_arm_1` | 圆桌分拣机械臂 1 |
| `robot_arm` | `robot_2` | `robot_arm_1` | 圆桌分拣机械臂 2 |
| `conveyor` | `out_conveyor_1` | `conveyor_1` | 出料传送带 1 |
| `conveyor` | `out_conveyor_2` | `conveyor_1` | 出料传送带 2 |
| `conveyor` | `out_conveyor_3` | `conveyor_1` | 出料传送带 3 |
| `conveyor` | `out_conveyor_4` | `conveyor_1` | 出料传送带 4 |

## 主要调度难点

- 圆桌呈现位一次只能被有限物料占用。
- 两台机械臂共享圆桌工件池。
- 目标出料传送带选择必须排除 blocked 传送带。

## 预期验证重点

- Agent 最终产物必须是 `SceneBehaviorGraph`。
- 行为规则必须使用 `trigger / guard / policy / action`。
- 事件必须先在 `event_bus.events` 注册，再被 route、rule 或 transition 引用。
- 涉及传送带时，必须建模 `conveyor_stop_points`、`conveyor_occupancy`、`conveyor_queues` 和 `conveyor_loads`。
