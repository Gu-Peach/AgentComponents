# conveyor

传送带设备分类目录。

| 文件              | 说明                                                            |
| ----------------- | --------------------------------------------------------------- |
| `schema.json`     | 传送带类型专属规范，继承外层 `common_device_spec.schema.json`。 |
| `template.json`   | 该设备类型的填写模板，后续新增同类设备时优先复制。              |
| `conveyor_1.json` | 传送带设备本体示例。                                            |
| `explain.md`      | 传送带字段语义说明，重点解释 `resources`、`motion_model` 和信号/流转关系。 |

## 关键特性

- 连续输送、出口等待、下游阻塞传播。
- 停留点 / 占位点生成：Runtime 根据 `entry`、`exit` 和 `stop_point_count` 插值得到点位。
- 通过 `entry`、`exit` 参与物料流转。
- 通过 `part_ready`、`blocked`、`capacity_available`、`stop_point_occupied`、`stop_point_released`、`done`、`release_waiting_material` 参与运行时信号协调。
- `runtime_contract.resources` 描述调度资源占用，用于判断并发、等待和阻塞。
- `type_specific_contract.motion_model` 描述物料运动机理，用于计算方向、速度、到位时间和前端动画。
- `type_specific_contract.stop_point_model` 描述停留点生成规则，用于排队、等待、阻塞和逐点推进。

## 核心区分

| 字段 | 负责的问题 |
| --- | --- |
| `transport_behaviors` | 设备能执行哪些输送行为。 |
| `runtime_contract.resources` | 当前动作是否能占用资源、是否需要等待或阻塞。 |
| `type_specific_contract.motion_model` | 动作执行后物料如何运动、如何计算到位。 |
| `type_specific_contract.stop_point_model` | 传送带停留点如何根据 entry/exit 坐标生成。 |
| `signal_ports` / `queue_policy` | 到达、阻塞、释放等运行事件如何和上下游设备通信。 |

## 停留点建模边界

| 层级 | 职责 |
| --- | --- |
| `DeviceSpec` | 定义传送带支持停留点生成，以及默认停留点数量。 |
| `SceneDocument` | 通过 `instances[].param_overrides.stop_point_count` 指定某条传送带实例在当前场景中使用几个停留点。 |
| `SceneBehaviorGraph` | 定义停留点如何参与行为规则、队列等待、阻塞恢复和下游释放。 |
| `RuntimeSnapshot` | 保存当前每个停留点被哪个物料或载具占用。 |
