# material_source_station

物料生产 / 上料台设备分类目录。

| 文件 | 说明 |
|---|---|
| `schema.json` | 物料来源工位类型专属规范，继承外层 `common_device_spec.schema.json`。 |
| `template.json` | 该设备类型的填写模板，后续新增同类设备时优先复制。 |
| `material_source_station_1.json` | 物料生产 / 上料台设备本体示例。 |

## 关键特性

- 生成、缓存或呈现待搬运物料。
- 通过 `output`、`buffer_area` 参与物料输出。
- 通过 `material_available`、`empty`、`done` 参与运行时信号协调。

