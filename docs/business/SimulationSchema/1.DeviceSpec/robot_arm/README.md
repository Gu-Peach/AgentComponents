# robot_arm

机械臂设备分类目录。

| 文件 | 说明 |
|---|---|
| `schema.json` | 机械臂类型专属规范，继承外层 `common_device_spec.schema.json`。 |
| `template.json` | 该设备类型的填写模板，后续新增同类设备时优先复制。 |
| `robot_arm_1.json` | 机械臂设备本体示例，保留 `urdf.joints` 和 `trajectoryConfig` 驱动格式。 |

## 关键特性

- 离散抓取、搬运、放置。
- 通过 `pick_area`、`place_area`、`tool_center_point` 参与场景编排。
- 通过 `start_pick`、`busy`、`done`、`error` 参与运行时信号协调。

