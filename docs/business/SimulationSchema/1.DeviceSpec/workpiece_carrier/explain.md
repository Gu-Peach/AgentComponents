# workpiece_carrier template 字段说明

本文用于解释 `workpiece_carrier/template.json` 中每个板块和字段的含义，作为后续编写物料载具 / 承载托盘类 `DeviceSpec` 的填写说明。

## 1. 模板定位

`workpiece_carrier` 表示能够承载物料并参与运输的载具，可覆盖托盘、载盘、夹具或移动承载板。它既不是纯被动物料，也不是主动输送设备，而是用于描述物料和输送设备之间的承载关系。

## 2. 占位符规则

| 后缀 | 含义 |
| --- | --- |
| `_required` | 必填字段。 |
| `_optional` | 可选字段。 |
| `a|b|required` | 枚举值提示。 |
| `{file}` | 模型文件名占位符。 |

## 3. 通用元信息

| 字段 | 含义 |
| --- | --- |
| `schema_id` | 当前模板唯一标识。 |
| `schema_type` | 当前 JSON 类型。 |
| `version` | 模板版本。 |
| `name` | 模板名称。 |
| `description` | 模板用途说明。 |
| `source.kind` / `source.path` | 模板来源和路径。 |
| `created_for` | 建模对象。 |
| `references` | 参考规范和示例。 |
| `notes` | 说明该类型可表示托盘、载盘、夹具或承载板。 |

## 4. 设备标识

| 字段 | 含义 |
| --- | --- |
| `device_spec_id` | 载具本体规范 ID。 |
| `device_type` | 固定为 `workpiece_carrier`。 |
| `display_name` | 展示名称。 |

## 5. 资产信息 `asset`

| 字段 | 含义 |
| --- | --- |
| `model_format` | 模型格式，可选。 |
| `model_key` | 载具模型路径或对象存储 key。 |

## 6. 参数定义 `params_schema`

| 字段 | 含义 |
| --- | --- |
| `slot_count` | 载具槽位数量，用于判断可承载多少个物料。 |
| `slot_count.type` | 参数类型，整数。 |
| `slot_count.default` | 默认槽位数量，必填。 |

## 7. 物理接口 `physical_interfaces`

| 接口 | 类型 | 方向 | 含义 |
| --- | --- | --- | --- |
| `load_surface` | `support` | `input` | 物料放置或装载表面。 |
| `carrier_bottom` | `support` | `bidirectional` | 载具底部支撑面，用于被传送带、升降台等设备承载。 |

| 字段 | 含义 |
| --- | --- |
| `interface_id` | 接口 ID。 |
| `kind` | 接口类型，载具主要是支撑接口。 |
| `direction` | 接口方向。 |
| `node_name` | 模型锚点节点名，可选。 |
| `material_classes` | 接口支持的物料类别。 |

## 8. 工艺流程口 `process_ports`

| 流程口 | 方向 | 含义 |
| --- | --- | --- |
| `flow_input` | `input` | 装载物料到载具。 |
| `flow_output` | `output` | 从载具卸载物料。 |

## 9. 信号端口 `signal_ports`

| 信号 | 方向 | 类型 | 含义 |
| --- | --- | --- | --- |
| `loaded` | `output` | `event` | 物料已装载到载具。 |
| `unloaded` | `output` | `event` | 物料已从载具卸载。 |

## 10. 接口绑定 `interface_bindings`

| 绑定关系 | 含义 |
| --- | --- |
| `flow_input -> load_surface` | 工艺装载映射到载具承载面。 |
| `flow_output -> load_surface` | 工艺卸载同样从载具承载面发生。 |

## 11. 输送行为 `transport_behaviors`

| 行为 | 类型 | 含义 |
| --- | --- | --- |
| `carry_material` | `passive_carry` | 承载物料，输出 `loaded`。 |
| `release_material` | `passive_release` | 释放物料，输出 `unloaded`。 |

| 字段 | 含义 |
| --- | --- |
| `input_physical_interface` | 物料进入载具的接口。 |
| `output_physical_interface` | 物料离开载具的接口。 |
| `output_signals` | 行为完成后输出的信号。 |

## 12. 运行契约 `runtime_contract`

| 字段 | 含义 |
| --- | --- |
| `fsm_states` | 载具运行时状态集合。 |
| `default_state` | 初始状态。 |
| `resources` | 载具槽位资源。 |
| `capacity.max_active_materials` | 最大可承载物料数量。 |

| 状态 | 含义 |
| --- | --- |
| `empty` | 载具为空。 |
| `loaded` | 已承载物料。 |
| `in_transport` | 载具正在被其他设备运输。 |

| 资源 | 含义 |
| --- | --- |
| `carrier_slots` | 载具槽位资源，`exclusive: false` 表示多个槽位可分别占用。 |

## 13. 载具专属契约 `type_specific_contract`

| 字段 | 含义 |
| --- | --- |
| `carrier_geometry` | 载具尺寸信息。 |
| `slots` | 槽位布局。 |
| `load_policy` | 装载策略。 |

### `carrier_geometry`

| 字段 | 含义 |
| --- | --- |
| `length_m` | 长度。 |
| `width_m` | 宽度。 |
| `height_m` | 高度，可选。 |

### `slots`

| 字段 | 含义 |
| --- | --- |
| `slot_count` | 槽位总数。 |
| `layout` | 槽位布局，如 `grid` 或 `custom`。 |
| `rows` | 行数，可选。 |
| `columns` | 列数，可选。 |

### `load_policy`

| 字段 | 含义 |
| --- | --- |
| `accepted_material_classes` | 允许装载的物料类别。 |
| `allow_partial_load` | 是否允许未装满也参与运输。 |

## 14. 字段协作关系

```text
load_surface        描述物料放置在载具上的位置
carrier_bottom      描述载具被其他运输设备承载的位置
slot_count / slots  描述可承载容量和布局
carry_material      形成物料与载具的绑定关系
release_material    解除物料与载具的绑定关系
loaded / unloaded   通知 Runtime 和下游设备承载状态变化
```

