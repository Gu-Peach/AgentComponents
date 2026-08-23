# workpiece

物料 / 工件设备分类目录。

| 文件 | 说明 |
|---|---|
| `schema.json` | 物料类型专属规范，继承外层 `common_device_spec.schema.json`。 |
| `template.json` | 该设备类型的填写模板，后续新增同类设备时优先复制。 |
| `workpiece_1.json` | 小型物料设备本体示例。 |

## 关键特性

- 通常是被动对象，不主动执行 transport behavior。
- 通过 `grasp_surface`、`bottom` 暴露可抓取和可放置约束。
- 通过 `picked`、`placed` 表达状态事件。

