# Scene 09：旋转台定位与机械臂下料

## 测试目的

验证 Agent 能否把场景 9 建模为可执行、可校验的 `SceneBehaviorGraph`，并正确处理该场景中的关键调度约束。

## 场景来源

- 图片：`docs/business/test/9.png`
- case：`docs/test/case/scene_09`
- 设备规范：`docs/business/SimulationSchema/1.DeviceSpec/`

## 用户目标摘要

出料台生成工件，人工搬运简化为旋转台固定工位生成工件；旋转台旋转 90 度后，机械臂抓取工件到工作台，工件消失。

## 设备与对象

| 类型 | 实例 | spec_id | 作用 |
|---|---|---|---|
| `material_source_station` | `source_station_1` | `material_source_station_1` | 物料来源，第一阶段可被旋转台生成替代 |
| `rotary_table` | `rotary_table_1` | `rotary_table_1` | 旋转定位台 |
| `robot_arm` | `robot_1` | `robot_arm_1` | 从旋转台到工作台的搬运机械臂 |
| `material_source_station` | `workstation_1` | `material_source_station_1` | 工作台 / 终点缓存，作为完成位置 |

## 主要调度难点

- 旋转台一次最多处理工位容量内的物料。
- 旋转过程中机械臂不能抓取。
- 工作台占用时机械臂等待。

## 预期验证重点

- Agent 最终产物必须是 `SceneBehaviorGraph`。
- 行为规则必须使用 `trigger / guard / policy / action`。
- 事件必须先在 `event_bus.events` 注册，再被 route、rule 或 transition 引用。
- 涉及传送带时，必须建模 `conveyor_stop_points`、`conveyor_occupancy`、`conveyor_queues` 和 `conveyor_loads`。
