# Scene 01 Validation Report

## 静态通过项

- 使用新方案链路：`DeviceSpec + SceneDocument + 用户目标 -> SceneBehaviorGraph -> RuntimeSnapshot`。
- 场景事实来自 `docs/business/SimulationSchema/2.SceneDocument/example.json`，包含两段主传送带、两条出料传送带、两台机械臂、托盘和 12 个工件。
- 传送带设备规范声明 `type_specific_contract.stop_point_model`，场景实例通过 `param_overrides.stop_point_count` 覆盖停留点数量。
- `SceneBehaviorGraph` 必须注册 `conveyor.stop_point_occupied`、`conveyor.stop_point_released`、`conveyor.blocked`、`conveyor.capacity_available`。
- 机器人设备规范必须声明 `pause_pick` / `resume_pick`，用于出料传送带 backpressure。

## 需要 Runtime Trace 验证的行为

- 当出口停留点被占用时，后续工件是否停在最近上游可用停留点。
- 当出口释放后，等待工件是否按队列和方向继续前进。
- 出料传送带无可用停留点或达到容量时，是否只暂停受影响机械臂的新抓取任务。
- 恢复阈值满足后，`robot.resume_pick` 是否正确释放等待中的机械臂。
- 两台机械臂并行 claim 时，同一工件是否永远不会被重复 claim。

## 当前假设

- 图 1 的上下出料传送带没有建模真实下游设备，工件到达出口后可直接离开系统。
- 主传送带仅搬运一个托盘，不启用出料缓存式超载 backpressure。
- 停留点坐标第一阶段只按 entry / exit 线性插值生成。
