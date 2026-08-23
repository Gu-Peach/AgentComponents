# lift_table

升降台设备分类目录。

| 文件 | 说明 |
|---|---|
| `schema.json` | 升降台类型专属规范，继承外层 `common_device_spec.schema.json`。 |
| `template.json` | 该设备类型的填写模板，后续新增同类设备时优先复制。 |
| `lift_table_1.json` | 升降台设备本体示例。 |

## 关键特性

- 在不同高度接口之间进行物料对接。
- 通过 `lower_dock`、`upper_dock`、`platform` 暴露物理接口。
- 通过 `move_to_level`、`at_level`、`moving`、`done`、`error` 参与运行时信号协调。

