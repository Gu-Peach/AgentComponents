# rotary_table

旋转台设备分类目录。

| 文件 | 说明 |
|---|---|
| `schema.json` | 旋转台类型专属规范，继承外层 `common_device_spec.schema.json`。 |
| `template.json` | 该设备类型的填写模板，后续新增同类设备时优先复制。 |
| `rotary_table_1.json` | 旋转台设备本体示例。 |

## 关键特性

- 多工位离散旋转定位。
- 通过 `station_a`、`station_b` 参与物料输入和输出。
- 通过 `rotate_to_station`、`at_station`、`occupied`、`rotating`、`done` 参与运行时信号协调。
