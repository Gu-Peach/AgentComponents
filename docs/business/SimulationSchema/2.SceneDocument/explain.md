# SceneDocument 字段说明

本文用于解释 `2.SceneDocument/schema.json` 与 `example.json` 中每个板块和字段的含义。`SceneDocument` 是场景事实层 schema，负责保存当前三维场景中“有哪些实例、它们在哪里、它们如何连接”。

## 1. schema 定位

`SceneDocument` 是八大 schema 中最核心的事实源之一。它不保存运行时状态，也不保存 Agent 的计划推理结果，只保存场景结构事实。

```text
DeviceSpec        定义可被引用的设备本体
SceneDocument     引入设备本体成为场景实例，并保存连接关系
SceneTransportSchema / SignalBusSchema  基于 SceneDocument 编译派生
```

## 2. `schema.json` 规范字段

| 字段 | 含义 |
| --- | --- |
| `schema_id` | 当前规范文件 ID。 |
| `schema_type` | 当前规范类型，示例为 `SceneDocumentSchema`。 |
| `version` | 规范版本。 |
| `name` | 规范名称。 |
| `description` | 规范用途说明。 |
| `source.kind` | 规范来源类型。 |
| `source.path` | 规范文件路径。 |
| `created_for` | 规范服务的建模目标。 |
| `references` | 依赖的通用规范和上游设备规范。 |
| `notes` | 设计边界说明，例如不保存当前运行时状态。 |
| `required_sections` | `SceneDocument` 必须包含的一级字段。 |
| `edge_contract` | 三类场景边的职责说明。 |

## 3. 必填板块 `required_sections`

| 板块 | 含义 |
| --- | --- |
| `scene_id` | 场景唯一 ID。 |
| `revision` | 场景修订号，每次结构变化递增。 |
| `instances` | 场景中引入的设备实例列表。 |
| `materials` | 场景中的物料实例列表。 |
| `process_edges` | 工艺流程边。 |
| `physical_edges` | 真实物理接口连接边。 |
| `signal_edges` | 信号连接边。 |
| `runtime_config` | 场景运行配置。 |

## 4. 三类边 `edge_contract`

| 边类型 | 含义 |
| --- | --- |
| `process_edges` | 流程画布层面的 `flow_output -> flow_input`，描述工艺上的物料流转关系。 |
| `physical_edges` | 真实物理接口之间的连接，通常由 `process_edges + interface_bindings` 编译得到。 |
| `signal_edges` | 设备信号端口之间的通讯关系，例如到料事件触发抓取命令。 |

## 5. 示例元信息

| 字段 | 含义 |
| --- | --- |
| `schema_id` | 示例文档 ID。 |
| `schema_type` | 示例类型，实际场景事实使用 `SceneDocument`。 |
| `name` | 示例名称。 |
| `description` | 示例场景说明。 |
| `source.kind` | 示例来源类型。 |
| `source.path` | 示例文件路径。 |
| `created_for` | 示例用途。 |
| `references` | 示例引用的设备本体和图片。 |
| `notes` | 示例中的简化假设。 |

## 6. 场景实例 `instances`

`instances` 描述场景里实际摆放了哪些设备，每个实例都引用某个 `DeviceSpec`。

| 字段 | 含义 |
| --- | --- |
| `instance_id` | 场景实例 ID，运行时和连接关系都引用它。 |
| `spec_id` | 引用的设备本体 ID，对应 `DeviceSpec.device_spec_id`。 |
| `device_type` | 实例类型，用于校验和筛选。 |
| `transform` | 设备在三维场景中的位姿。 |
| `transform.position` | 位置 `[x, y, z]`。 |
| `transform.rotation_euler` | 欧拉角旋转 `[x, y, z]`。 |
| `transform.scale` | 缩放 `[x, y, z]`。 |
| `params` | 对设备本体默认参数的场景级覆盖。 |

## 7. 物料实例 `materials`

| 字段 | 含义 |
| --- | --- |
| `material_id` | 物料实例 ID。 |
| `spec_id` | 引用的物料本体 `DeviceSpec`。 |
| `located_at` | 物料初始位置，可指向设备接口、载具槽位或库位。 |

## 8. 工艺流程边 `process_edges`

| 字段 | 含义 |
| --- | --- |
| `edge_id` | 工艺边 ID。 |
| `source` | 源流程口，格式通常为 `instance_id.process_port`。 |
| `target` | 目标流程口，格式通常为 `instance_id.process_port`。 |
| `edge_type` | 边类型，例如 `material_flow`。 |

`process_edges` 是工艺层事实，表达“物料应该按什么工艺顺序流转”。

## 9. 物理连接边 `physical_edges`

| 字段 | 含义 |
| --- | --- |
| `edge_id` | 物理边 ID。 |
| `source` | 源物理接口，格式通常为 `instance_id.physical_interface`。 |
| `target` | 目标物理接口。 |
| `compiled_from` | 该物理边由哪条工艺边编译得到。 |

`physical_edges` 是执行层事实，表达“物料实际从哪个三维接口到哪个三维接口”。

## 10. 信号连接边 `signal_edges`

| 字段 | 含义 |
| --- | --- |
| `edge_id` | 信号边 ID。 |
| `source` | 源信号端口，格式通常为 `instance_id.signal_port`。 |
| `target` | 目标信号端口。 |
| `edge_type` | 信号边类型，例如 `control_signal`。 |

`signal_edges` 只定义静态连接关系，实际信号值和等待队列由 `SignalBusSchema` 与 `RuntimeSnapshot` 管理。

## 11. 运行配置 `runtime_config`

| 字段 | 含义 |
| --- | --- |
| `deadlock_detection` | 是否启用死锁检测。 |
| `default_signal_timeout_s` | 默认信号等待超时时间，单位秒。 |

## 12. 下游使用方式

```text
SceneDocument.instances + DeviceSpec
  -> 校验设备接口、信号口和行为能力

SceneDocument.process_edges + interface_bindings
  -> 编译 physical_edges / SceneTransportSchema

SceneDocument.signal_edges + SimPlan.signal_rules
  -> 编译 SignalBusSchema
```

