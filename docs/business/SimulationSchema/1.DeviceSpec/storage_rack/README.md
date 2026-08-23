# storage_rack

存储柜 / 货架设备分类目录。

| 文件 | 说明 |
|---|---|
| `schema.json` | 存储柜类型专属规范，继承外层 `common_device_spec.schema.json`。 |
| `template.json` | 该设备类型的填写模板，后续新增同类设备时优先复制。 |
| `storage_rack_1.json` | 存储柜 / 货架设备本体示例。 |

## 关键特性

- 提供库位、容量和预约策略。
- 通过 `cell_input`、`cell_output` 参与入库和出库。
- 通过 `cell_available`、`cell_full`、`stored`、`released` 参与运行时信号协调。

