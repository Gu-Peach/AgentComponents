# Scene 04：传送带中段机械臂加工模拟

## 测试目的

验证 Agent 能否把场景 4 建模为可执行、可校验的 `SceneBehaviorGraph`，并正确处理该场景中的关键调度约束。

## 场景来源

- 图片：`docs/business/test/4.png`
- case：`docs/test/case/scene_04`
- 设备规范：`docs/business/SimulationSchema/1.DeviceSpec/`

## 用户目标摘要

传送带起点直接生成或接收物料，物料移动到中间加工停留点后由机械臂执行固定位置操作，完成后继续沿传送带输出。

## 设备与对象

| 类型 | 实例 | spec_id | 作用 |
|---|---|---|---|
| `material_source_station` | `source_station_1` | `material_source_station_1` | 传送带起点物料来源 |
| `conveyor` | `main_conveyor_1` | `conveyor_1` | 中段加工主传送带 |
| `robot_arm` | `robot_1` | `robot_arm_1` | 中段加工机械臂 |
| `robot_arm` | `robot_2` | `robot_arm_1` | 备用或第二加工机械臂 |

## 主要调度难点

- 加工停留点一次只处理一个物料。
- 物料未加工完成不能越过加工点。
- 后续物料必须在上游停留点等待。

## 预期验证重点

- Agent 最终产物必须是 `SceneBehaviorGraph`。
- 行为规则必须使用 `trigger / guard / policy / action`。
- 事件必须先在 `event_bus.events` 注册，再被 route、rule 或 transition 引用。
- 涉及传送带时，必须建模 `conveyor_stop_points`、`conveyor_occupancy`、`conveyor_queues` 和 `conveyor_loads`。
