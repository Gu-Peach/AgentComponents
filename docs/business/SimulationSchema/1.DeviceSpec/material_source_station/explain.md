# material_source_station template 字段说明

本文用于解释 `material_source_station/template.json` 中每个板块和字段的含义，作为后续编写物料生产 / 上料台类 `DeviceSpec` 的填写说明。

## 1. 模板定位

`material_source_station` 表示物料来源工位，负责按节拍生成、缓存或提供物料。它强调“物料来源 / 上料”，不默认表达复杂加工中心的工艺逻辑。

## 2. 占位符规则

| 后缀 | 含义 |
| --- | --- |
| `_required` | 必填字段。 |
| `_optional` | 可选字段。 |
| `a|b|required` | 枚举提示，需选择真实策略。 |
| `{file}` | 模型文件名占位符。 |

## 3. 通用元信息

| 字段 | 含义 |
| --- | --- |
| `schema_id` | 当前模板唯一标识。 |
| `schema_type` | 当前 JSON 类型。 |
| `version` | 模板版本。 |
| `name` | 模板名称。 |
| `description` | 模板用途。 |
| `source.kind` / `source.path` | 来源类型和文件路径。 |
| `created_for` | 建模对象。 |
| `references` | 参考规范和示例。 |
| `notes` | 建模边界说明。 |

## 4. 设备标识

| 字段 | 含义 |
| --- | --- |
| `device_spec_id` | 物料来源工位本体 ID。 |
| `device_type` | 固定为 `material_source_station`。 |
| `display_name` | 展示名称。 |

## 5. 资产信息 `asset`

| 字段 | 含义 |
| --- | --- |
| `model_format` | 模型格式，可选。 |
| `model_key` | 模型路径或对象存储 key。 |

## 6. 参数定义 `params_schema`

| 字段 | 含义 |
| --- | --- |
| `cycle_time_s` | 生成或准备一个物料的节拍时间，单位秒。 |
| `cycle_time_s.type` | 参数类型。 |
| `cycle_time_s.default` | 默认节拍，必填。 |
| `cycle_time_s.unit` | 单位。 |
| `buffer_capacity` | 工位缓存容量。 |
| `buffer_capacity.type` | 参数类型，整数。 |
| `buffer_capacity.default` | 默认缓存容量，必填。 |

## 7. 物理接口 `physical_interfaces`

| 接口 | 类型 | 方向 | 含义 |
| --- | --- | --- | --- |
| `output` | `material` | `output` | 物料对外输出接口。 |
| `buffer_area` | `storage` | `bidirectional` | 物料缓存区域。 |

| 字段 | 含义 |
| --- | --- |
| `interface_id` | 接口 ID。 |
| `kind` | 接口类型，如物料输出或缓存。 |
| `direction` | 接口方向。 |
| `node_name` | 模型锚点节点名。 |
| `material_classes` | 支持输出或缓存的物料类型。 |

## 8. 工艺流程口 `process_ports`

| 流程口 | 方向 | 含义 |
| --- | --- | --- |
| `flow_output` | `output` | 物料来源工位在工艺流程中的输出。 |

该设备通常没有 `flow_input`，因为它是物料流转路线的起点。

## 9. 信号端口 `signal_ports`

| 信号 | 方向 | 类型 | 含义 |
| --- | --- | --- | --- |
| `material_available` | `output` | `event` | 有物料可被下游取走。 |
| `empty` | `output` | `boolean` | 工位当前无可用物料。 |
| `done` | `output` | `event` | 本次生产或上料动作完成。 |

## 10. 接口绑定 `interface_bindings`

| 绑定关系 | 含义 |
| --- | --- |
| `flow_output -> output` | 工艺输出映射到真实物料输出接口。 |

## 11. 输送行为 `transport_behaviors`

| 行为 | 类型 | 含义 |
| --- | --- | --- |
| `produce_material` | `material_generation` | 生成物料并放入缓存区，输出 `material_available` 和 `done`。 |
| `present_material` | `material_handoff` | 将缓存区物料呈递到输出接口，输出 `material_available`。 |

| 字段 | 含义 |
| --- | --- |
| `input_physical_interface` | 行为输入接口，如缓存区。 |
| `output_physical_interface` | 行为输出接口。 |
| `output_signals` | 行为完成或可取料时输出的信号。 |

## 12. 运行契约 `runtime_contract`

| 字段 | 含义 |
| --- | --- |
| `fsm_states` | 来源工位状态集合。 |
| `default_state` | 初始状态。 |
| `resources` | 运行资源，如缓存资源。 |
| `capacity.max_active_materials` | 缓存区最大物料数。 |

| 状态 | 含义 |
| --- | --- |
| `idle` | 空闲。 |
| `producing` | 正在生产或准备物料。 |
| `material_ready` | 有物料可取。 |
| `empty` | 当前无物料。 |
| `error` | 异常状态。 |

| 资源 | 含义 |
| --- | --- |
| `source_buffer` | 物料来源工位的缓存资源，可非独占。 |

## 13. 来源工位专属契约 `type_specific_contract`

| 字段 | 含义 |
| --- | --- |
| `production_policy` | 物料生成策略。 |
| `buffer` | 缓存策略。 |
| `output_material_spec` | 该工位输出的物料 `DeviceSpec`。 |

### `production_policy`

| 字段 | 含义 |
| --- | --- |
| `mode` | 生产模式，如按需 `on_demand` 或周期 `periodic`。 |
| `cycle_time_param` | 节拍参数引用，通常为 `cycle_time_s`。 |

### `buffer`

| 字段 | 含义 |
| --- | --- |
| `capacity_param` | 缓存容量引用，通常为 `buffer_capacity`。 |
| `release_policy` | 缓存释放策略，如被取走后释放。 |

## 14. 字段协作关系

```text
cycle_time_s / production_policy  决定物料生成节拍
buffer_capacity / buffer_area     决定可缓存多少物料
produce_material                  生成物料并写入缓存
present_material                  将物料呈递到 output
material_available / empty        通知下游是否可以取料
output_material_spec              约束生成出来的物料类型
```

