# workpiece_carrier

物料载具 / 承载托盘设备分类目录。

| 文件 | 说明 |
|---|---|
| `schema.json` | 物料载具类型专属规范，继承外层 `common_device_spec.schema.json`。 |
| `template.json` | 该设备类型的填写模板，后续新增同类设备时优先复制。 |
| `carrier_tray_1.json` | 承载托盘 / 物料载具设备本体示例。 |

## 关键特性

- 可承载多个物料并被传送带或机械臂搬运。
- 通过 `load_surface`、`carrier_bottom` 暴露装载和承载接口。
- 通过 `loaded`、`unloaded` 表达装载状态变化。

