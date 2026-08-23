# storage_rack template 字段说明

本文用于解释 `storage_rack/template.json` 中每个板块和字段的含义，作为后续编写存储柜 / 货架类 `DeviceSpec` 的填写说明。

## 1. 模板定位

`storage_rack` 表示静态存储资源，用于描述库位、容量、入库、出库和库位预约能力。它不是自动出入库设备本体；如果后续需要主动搬运机构，可扩展为 `storage_system` 或 `automated_storage`。

## 2. 占位符规则

| 后缀 | 含义 |
| --- | --- |
| `_required` | 必填字段。 |
| `_optional` | 可选字段。 |
| `a|b|required` | 枚举提示。 |
| `{file}` | 模型文件名占位符。 |

## 3. 通用元信息

| 字段 | 含义 |
| --- | --- |
| `schema_id` | 当前模板唯一标识。 |
| `schema_type` | JSON 类型。 |
| `version` | 模板版本。 |
| `name` | 模板名称。 |
| `description` | 模板用途说明。 |
| `source.kind` / `source.path` | 来源类型和路径。 |
| `created_for` | 建模对象。 |
| `references` | 参考规范和示例。 |
| `notes` | 当前模板适用边界说明。 |

## 4. 设备标识

| 字段 | 含义 |
| --- | --- |
| `device_spec_id` | 存储柜本体规范 ID。 |
| `device_type` | 固定为 `storage_rack`。 |
| `display_name` | 展示名称。 |

## 5. 资产信息 `asset`

| 字段 | 含义 |
| --- | --- |
| `model_format` | 模型格式，可选。 |
| `model_key` | 模型路径或对象存储 key。 |

## 6. 参数定义 `params_schema`

| 字段 | 含义 |
| --- | --- |
| `rows` | 存储柜行数。 |
| `rows.type` | 参数类型，整数。 |
| `rows.default` | 默认行数，必填。 |
| `columns` | 存储柜列数。 |
| `columns.type` | 参数类型，整数。 |
| `columns.default` | 默认列数，必填。 |

## 7. 物理接口 `physical_interfaces`

| 接口 | 类型 | 方向 | 含义 |
| --- | --- | --- | --- |
| `cell_input` | `material` | `input` | 入库接口。 |
| `cell_output` | `material` | `output` | 出库接口。 |

| 字段 | 含义 |
| --- | --- |
| `interface_id` | 接口 ID。 |
| `kind` | 接口类型。 |
| `direction` | 接口方向。 |
| `node_name` | 模型锚点节点名。 |
| `material_classes` | 支持存放的物料类型。 |

## 8. 工艺流程口 `process_ports`

| 流程口 | 方向 | 含义 |
| --- | --- | --- |
| `flow_input` | `input` | 工艺入库入口。 |
| `flow_output` | `output` | 工艺出库出口。 |

## 9. 信号端口 `signal_ports`

| 信号 | 方向 | 类型 | 含义 |
| --- | --- | --- | --- |
| `cell_available` | `output` | `event` | 有可用库位。 |
| `cell_full` | `output` | `boolean` | 库位已满或目标库位不可用。 |
| `stored` | `output` | `event` | 物料已入库。 |
| `released` | `output` | `event` | 物料已出库释放。 |

## 10. 接口绑定 `interface_bindings`

| 绑定关系 | 含义 |
| --- | --- |
| `flow_input -> cell_input` | 工艺入库映射到真实入库接口。 |
| `flow_output -> cell_output` | 工艺出库映射到真实出库接口。 |

## 11. 输送行为 `transport_behaviors`

| 行为 | 类型 | 含义 |
| --- | --- | --- |
| `reserve_cell` | `storage_reservation` | 预约可用库位，输出 `cell_available`。 |
| `store_to_cell` | `storage` | 从 `cell_input` 入库，输出 `stored` 和 `cell_full`。 |
| `release_from_cell` | `storage_release` | 从库位释放到 `cell_output`，输出 `released`。 |

## 12. 运行契约 `runtime_contract`

| 字段 | 含义 |
| --- | --- |
| `fsm_states` | 存储柜状态集合。 |
| `default_state` | 初始状态。 |
| `resources` | 存储资源集合。 |
| `capacity.max_active_materials` | 最大可存储物料数量，通常为 `rows * columns`。 |

| 状态 | 含义 |
| --- | --- |
| `idle` | 空闲。 |
| `reserving` | 正在预约库位。 |
| `storing` | 正在入库。 |
| `releasing` | 正在出库。 |
| `full` | 库位满。 |
| `error` | 异常状态。 |

| 资源 | 含义 |
| --- | --- |
| `storage_cells` | 库位资源，`exclusive: false` 表示多个库位可以分别占用。 |

## 13. 存储柜专属契约 `type_specific_contract`

| 字段 | 含义 |
| --- | --- |
| `cells` | 库位布局和 ID。 |
| `capacity` | 总容量和支持物料类别。 |
| `reservation_policy` | 库位预约策略。 |

### `cells`

| 字段 | 含义 |
| --- | --- |
| `rows` | 库位行数。 |
| `columns` | 库位列数。 |
| `cell_ids` | 库位 ID 列表。 |

### `capacity`

| 字段 | 含义 |
| --- | --- |
| `total_cells` | 总库位数。 |
| `material_classes` | 支持存储的物料类别。 |

### `reservation_policy`

| 字段 | 含义 |
| --- | --- |
| `strategy` | 库位选择策略，如 `first_available` 或 `nearest`。 |
| `release_on` | 出库或释放库位的触发信号。 |

## 14. 字段协作关系

```text
rows / columns / cell_ids     描述库位结构
storage_cells                 作为 Runtime 可占用资源
reserve_cell                  选择可用库位
store_to_cell / release_from_cell  执行入库和出库语义
cell_available / cell_full    通知调度器库位可用性
stored / released             通知入库、出库动作完成
```

