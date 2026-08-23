# rotary_table template 字段说明

本文用于解释 `rotary_table/template.json` 中每个板块和字段的含义，作为后续编写旋转台类 `DeviceSpec` 的填写说明。

## 1. 模板定位

`rotary_table` 表示多工位旋转定位设备。它负责在离散工位之间旋转物料或载具，使上料、处理、下料等不同工位在空间上轮转对接。

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
| `schema_type` | JSON 类型。 |
| `version` | 模板版本。 |
| `name` | 模板名称。 |
| `description` | 模板用途说明。 |
| `source.kind` / `source.path` | 来源类型和路径。 |
| `created_for` | 建模对象。 |
| `references` | 参考规范和示例。 |
| `notes` | 说明旋转台默认按离散工位 indexing 建模。 |

## 4. 设备标识

| 字段 | 含义 |
| --- | --- |
| `device_spec_id` | 旋转台本体规范 ID。 |
| `device_type` | 固定为 `rotary_table`。 |
| `display_name` | 展示名称。 |

## 5. 资产信息 `asset`

| 字段 | 含义 |
| --- | --- |
| `model_format` | 模型格式，可选。 |
| `model_key` | 模型路径或对象存储 key。 |

## 6. 参数定义 `params_schema`

| 字段 | 含义 |
| --- | --- |
| `rotate_speed_deg_s` | 旋转速度，单位度/秒。 |
| `rotate_speed_deg_s.type` | 参数类型。 |
| `rotate_speed_deg_s.default` | 默认旋转速度，必填。 |
| `rotate_speed_deg_s.unit` | 单位。 |
| `station_count` | 工位数量。 |
| `station_count.type` | 参数类型，整数。 |
| `station_count.default` | 默认工位数，必填。 |

## 7. 物理接口 `physical_interfaces`

| 接口 | 类型 | 方向 | 含义 |
| --- | --- | --- | --- |
| `station_a` | `material` | `bidirectional` | 工位 A，可接收或释放物料。 |
| `station_b` | `material` | `bidirectional` | 工位 B，可接收或释放物料。 |

| 字段 | 含义 |
| --- | --- |
| `interface_id` | 工位接口 ID。 |
| `kind` | 接口类型。 |
| `direction` | 工位接口方向。 |
| `node_name` | GLB 模型中的工位锚点。 |
| `material_classes` | 支持的物料类别。 |

## 8. 工艺流程口 `process_ports`

| 流程口 | 方向 | 含义 |
| --- | --- | --- |
| `flow_input` | `input` | 工艺进入旋转台。 |
| `flow_output` | `output` | 工艺从旋转台流出。 |

## 9. 信号端口 `signal_ports`

| 信号 | 方向 | 类型 | 含义 |
| --- | --- | --- | --- |
| `rotate_to_station` | `input` | `command` | 命令旋转台转到指定工位。 |
| `at_station` | `output` | `event` | 已到达目标工位。 |
| `occupied` | `output` | `boolean` | 旋转台工位或转盘当前被物料占用。 |
| `rotating` | `output` | `boolean` | 正在旋转。 |
| `done` | `output` | `event` | 当前旋转或交接动作完成。 |

## 10. 接口绑定 `interface_bindings`

| 绑定关系 | 含义 |
| --- | --- |
| `flow_input -> station_a` | 工艺输入默认映射到工位 A。 |
| `flow_output -> station_b` | 工艺输出默认映射到工位 B。 |

## 11. 输送行为 `transport_behaviors`

| 行为 | 类型 | 含义 |
| --- | --- | --- |
| `accept_material` | `material_handoff` | 从 `station_a` 接收物料，并输出占用状态。 |
| `rotate_to_station` | `rotary_motion` | 根据命令旋转到目标工位，输出 `rotating`、`at_station`、`done`。 |
| `release_material` | `material_handoff` | 从 `station_b` 释放物料，并更新占用状态。 |

## 12. 运行契约 `runtime_contract`

| 字段 | 含义 |
| --- | --- |
| `fsm_states` | 旋转台状态集合。 |
| `default_state` | 初始状态。 |
| `resources` | 调度资源集合。 |
| `capacity.max_active_materials` | 工位或转盘可同时承载的物料数量。 |

| 状态 | 含义 |
| --- | --- |
| `idle` | 空闲。 |
| `occupied` | 已有物料占用。 |
| `rotating` | 正在旋转。 |
| `at_station` | 已到达指定工位。 |
| `error` | 异常状态。 |

| 资源 | 含义 |
| --- | --- |
| `rotary_plate` | 旋转盘资源，`exclusive: true` 表示旋转动作独占转盘。 |

## 13. 旋转台专属契约 `type_specific_contract`

| 字段 | 含义 |
| --- | --- |
| `stations` | 离散工位定义。 |
| `rotation_axis` | 旋转轴。 |
| `indexing_policy` | 分度定位策略。 |

### `stations[]`

| 字段 | 含义 |
| --- | --- |
| `station_id` | 工位 ID。 |
| `angle_deg` | 工位对应角度。 |

### `rotation_axis`

旋转轴向量，模板中 `[0, 1, 0]` 表示绕局部 y 轴旋转。

### `indexing_policy`

| 字段 | 含义 |
| --- | --- |
| `mode` | 定位模式；`discrete` 表示离散工位定位。 |
| `speed_param` | 旋转速度参数引用，通常为 `rotate_speed_deg_s`。 |
| `tolerance_deg` | 工位到位角度容差，可选。 |

## 14. 字段协作关系

```text
stations / angle_deg       定义可旋转到的离散工位
rotation_axis              定义旋转方向
indexing_policy            定义分度定位方式
station_a / station_b      定义物料交接工位
rotary_plate               控制旋转动作互斥
rotate_to_station / at_station  形成旋转命令和到位通知
```

