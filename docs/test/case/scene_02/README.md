# Scene 02：多机械臂远端优先托盘分拣线

## 测试目的

验证 Agent 能否把场景 2 建模为可执行、可校验的 `SceneBehaviorGraph`，并正确处理该场景中的关键调度约束。

## 场景来源

- 图片：`docs/business/test/2.png`
- case：`docs/test/case/scene_02`
- 设备规范：`docs/business/SimulationSchema/1.DeviceSpec/`

## 用户目标摘要

左侧出料口间隔输出承载 12 个工件的托盘，托盘沿长主传送带移动到三台机械臂工位；系统优先把新托盘送到最远端空闲机械臂，三台机械臂全忙时主线和出料口暂停。

## 设备与对象

| 类型 | 实例 | spec_id | 作用 |
|---|---|---|---|
| `material_source_station` | `pallet_source_1` | `material_source_station_1` | 间隔生成装有 12 个工件的托盘 |
| `conveyor` | `main_conveyor_1` | `conveyor_1` | 长主传送带，沿三台机械臂工位分配托盘 |
| `robot_arm` | `robot_1` | `robot_arm_1` | 近端分拣机械臂 |
| `robot_arm` | `robot_2` | `robot_arm_1` | 中端分拣机械臂 |
| `robot_arm` | `robot_3` | `robot_arm_1` | 远端分拣机械臂 |
| `conveyor` | `robot_1_out_conveyor` | `conveyor_1` | robot_1 对应出料传送带 |
| `conveyor` | `robot_2_out_conveyor` | `conveyor_1` | robot_2 对应出料传送带 |
| `conveyor` | `robot_3_out_conveyor` | `conveyor_1` | robot_3 对应出料传送带 |

## 主要调度难点

- 远端优先分配托盘：robot_3 -> robot_2 -> robot_1。
- 三台机械臂全忙时，主传送带和出料口暂停。
- 所有传送带必须按停留点占用推进。
- 各机器人对应出料传送带需要 backpressure。

## 预期验证重点

- Agent 最终产物必须是 `SceneBehaviorGraph`。
- 行为规则必须使用 `trigger / guard / policy / action`。
- 事件必须先在 `event_bus.events` 注册，再被 route、rule 或 transition 引用。
- 涉及传送带时，必须建模 `conveyor_stop_points`、`conveyor_occupancy`、`conveyor_queues` 和 `conveyor_loads`。
