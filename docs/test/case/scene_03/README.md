# Scene 03：双机械臂接力运输机构

## 测试目的

验证 Agent 能否把场景 3 建模为可执行、可校验的 `SceneBehaviorGraph`，并正确处理该场景中的关键调度约束。

## 场景来源

- 图片：`docs/business/test/3.png`
- case：`docs/test/case/scene_03`
- 设备规范：`docs/business/SimulationSchema/1.DeviceSpec/`

## 用户目标摘要

右侧上料台产生物料，物料经右侧传送带到达终点后由第一台机械臂搬到固定交接位，第二台机械臂再从交接位搬到左侧传送带输出。

## 设备与对象

| 类型 | 实例 | spec_id | 作用 |
|---|---|---|---|
| `material_source_station` | `source_station_1` | `material_source_station_1` | 右侧物料来源 |
| `conveyor` | `right_in_conveyor_1` | `conveyor_1` | 输入传送带 |
| `robot_arm` | `robot_1` | `robot_arm_1` | 从输入传送带搬到交接位 |
| `robot_arm` | `robot_2` | `robot_arm_1` | 从交接位搬到输出传送带 |
| `conveyor` | `left_out_conveyor_1` | `conveyor_1` | 输出传送带 |

## 主要调度难点

- 交接位一次只能放一个工件。
- 输入传送带出口占用时后续工件停在上游停留点。
- 输出传送带入口不可接收时 robot_2 等待。

## 预期验证重点

- Agent 最终产物必须是 `SceneBehaviorGraph`。
- 行为规则必须使用 `trigger / guard / policy / action`。
- 事件必须先在 `event_bus.events` 注册，再被 route、rule 或 transition 引用。
- 涉及传送带时，必须建模 `conveyor_stop_points`、`conveyor_occupancy`、`conveyor_queues` 和 `conveyor_loads`。
