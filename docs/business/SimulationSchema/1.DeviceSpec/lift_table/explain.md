# lift_table template 字段说明

本文用于解释 `lift_table/template.json` 中每个板块和字段的含义，作为后续编写升降台类 `DeviceSpec` 的填写说明。

## 1. 模板定位

`lift_table` 表示可在不同高度层之间转移物料的升降设备。它负责接收物料、垂直移动到目标高度、与上下游设备对接并释放物料。

## 2. 占位符规则

| 后缀 | 含义 |
| --- | --- |
| `_required` | 必填字段。 |
| `_optional` | 可选字段。 |
| `{file}` | 模型文件名占位符。 |

## 3. 通用元信息

| 字段 | 含义 |
| --- | --- |
| `schema_id` | 当前模板唯一标识。 |
| `schema_type` | JSON 类型，模板为 `DeviceSpecTemplate`。 |
| `version` | 模板版本。 |
| `name` | 模板名称。 |
| `description` | 模板用途说明。 |
| `source.kind` / `source.path` | 模板来源和路径。 |
| `created_for` | 建模对象。 |
| `references` | 引用的通用规范、类型规范和示例。 |
| `notes` | 核心接口说明，模板中强调 `lower_dock`、`upper_dock`、`platform`。 |

## 4. 设备标识

| 字段 | 含义 |
| --- | --- |
| `device_spec_id` | 升降台本体规范 ID。 |
| `device_type` | 固定为 `lift_table`。 |
| `display_name` | 展示名称。 |

## 5. 资产信息 `asset`

| 字段 | 含义 |
| --- | --- |
| `model_format` | 模型格式，可选。 |
| `model_key` | 模型路径或对象存储 key。 |

## 6. 参数定义 `params_schema`

| 字段 | 含义 |
| --- | --- |
| `lift_speed_mps` | 升降速度，单位米/秒。 |
| `lift_speed_mps.type` | 参数类型。 |
| `lift_speed_mps.default` | 默认升降速度，必填。 |
| `lift_speed_mps.unit` | 单位。 |
| `max_height_m` | 最大升降高度。 |
| `max_height_m.default` | 默认最大高度，必填。 |

## 7. 物理接口 `physical_interfaces`

| 接口 | 类型 | 方向 | 含义 |
| --- | --- | --- | --- |
| `lower_dock` | `material` | `bidirectional` | 下层对接口，可接收或释放物料。 |
| `upper_dock` | `material` | `bidirectional` | 上层对接口，可接收或释放物料。 |
| `platform` | `support` | `bidirectional` | 升降平台承载面。 |

| 字段 | 含义 |
| --- | --- |
| `interface_id` | 接口 ID。 |
| `kind` | 接口类型。 |
| `direction` | 接口方向。 |
| `node_name` | GLB 模型中的锚点节点名。 |
| `material_classes` | 支持承载或交接的物料类型。 |

## 8. 工艺流程口 `process_ports`

| 流程口 | 方向 | 含义 |
| --- | --- | --- |
| `flow_input` | `input` | 工艺流入升降台。 |
| `flow_output` | `output` | 工艺从升降台流出。 |

## 9. 信号端口 `signal_ports`

| 信号 | 方向 | 类型 | 含义 |
| --- | --- | --- | --- |
| `move_to_level` | `input` | `command` | 命令升降台移动到指定高度层。 |
| `at_level` | `output` | `event` | 升降台到达目标高度层。 |
| `moving` | `output` | `boolean` | 升降台正在移动。 |
| `done` | `output` | `event` | 当前升降动作完成。 |
| `error` | `output` | `event` | 升降动作失败或设备异常。 |

## 10. 接口绑定 `interface_bindings`

| 绑定关系 | 含义 |
| --- | --- |
| `flow_input -> lower_dock` | 工艺输入默认映射到下层对接口。 |
| `flow_output -> upper_dock` | 工艺输出默认映射到上层对接口。 |

## 11. 输送行为 `transport_behaviors`

| 行为 | 类型 | 含义 |
| --- | --- | --- |
| `accept_material` | `material_handoff` | 从 `lower_dock` 接收物料到 `platform`。 |
| `lift_to_level` | `vertical_motion` | 根据 `move_to_level` 执行竖直升降，输出 `moving`、`at_level`、`done`。 |
| `release_material` | `material_handoff` | 从 `platform` 向 `upper_dock` 释放物料。 |

| 字段 | 含义 |
| --- | --- |
| `input_physical_interface` | 行为输入接口。 |
| `output_physical_interface` | 行为输出接口。 |
| `input_signals` | 行为启动命令或信号。 |
| `output_signals` | 行为产生的运行信号。 |

## 12. 运行契约 `runtime_contract`

| 字段 | 含义 |
| --- | --- |
| `fsm_states` | 升降台状态集合。 |
| `default_state` | 初始状态。 |
| `resources` | 调度资源集合。 |
| `capacity.max_active_materials` | 平台同一时间可承载物料数量。 |

| 状态 | 含义 |
| --- | --- |
| `idle` | 空闲。 |
| `loading` | 正在接收物料。 |
| `moving` | 正在升降。 |
| `at_lower` | 位于下层。 |
| `at_upper` | 位于上层。 |
| `error` | 异常状态。 |

| 资源 | 含义 |
| --- | --- |
| `lift_platform` | 升降平台资源，`exclusive: true` 表示同一时间只能服务一个物料或载具。 |

## 13. 升降台专属契约 `type_specific_contract`

| 字段 | 含义 |
| --- | --- |
| `height_levels` | 可对接高度层列表。 |
| `lift_motion` | 升降运动模型。 |
| `dock_policy` | 对接策略。 |

### `height_levels[]`

| 字段 | 含义 |
| --- | --- |
| `level_id` | 高度层 ID，如 `lower`、`upper`。 |
| `height_m` | 该高度层的绝对或局部高度，单位米。 |

### `lift_motion`

| 字段 | 含义 |
| --- | --- |
| `axis` | 升降方向向量，模板中 `[0, 1, 0]` 表示沿局部 y 轴。 |
| `speed_param` | 速度参数引用，通常为 `lift_speed_mps`。 |

### `dock_policy`

| 字段 | 含义 |
| --- | --- |
| `requires_level_match` | 是否要求平台高度与对接口高度匹配后才能交接。 |
| `tolerance_m` | 对接高度容差，可选。 |

## 14. 字段协作关系

```text
height_levels / dock_policy   决定升降台能在哪些高度对接
lower_dock / upper_dock       定义上下游物料接口
platform / lift_platform      定义被占用的承载资源
move_to_level / at_level      驱动高度切换和到位通知
lift_motion                   计算升降方向、速度和到位时间
```

