# Scene 07：机床旁机械臂加工转运

## 测试目的

验证 Agent 能否把场景 7 建模为可执行、可校验的 `SceneBehaviorGraph`，并正确处理该场景中的关键调度约束。

## 场景来源

- 图片：`docs/business/test/7.png`
- case：`docs/test/case/scene_07`
- 设备规范：`docs/business/SimulationSchema/1.DeviceSpec/`

## 用户目标摘要

输入传送带持续送入物料，机械臂从输入传送带取料到固定加工位模拟加工，完成后放到输出传送带。

## 设备与对象

| 类型 | 实例 | spec_id | 作用 |
|---|---|---|---|
| `material_source_station` | `source_station_1` | `material_source_station_1` | 输入物料来源 |
| `conveyor` | `input_conveyor_1` | `conveyor_1` | 输入传送带 |
| `robot_arm` | `robot_1` | `robot_arm_1` | 机床上下料机械臂 |
| `conveyor` | `output_conveyor_1` | `conveyor_1` | 输出传送带 |

## 主要调度难点

- 加工位一次只能处理一个物料。
- 输出传送带 blocked 时 robot_1 不能开始新的放料。
- 输入传送带出口占用时后续物料排队。

## 预期验证重点

- Agent 最终产物必须是 `SceneBehaviorGraph`。
- 行为规则必须使用 `trigger / guard / policy / action`。
- 事件必须先在 `event_bus.events` 注册，再被 route、rule 或 transition 引用。
- 涉及传送带时，必须建模 `conveyor_stop_points`、`conveyor_occupancy`、`conveyor_queues` 和 `conveyor_loads`。
