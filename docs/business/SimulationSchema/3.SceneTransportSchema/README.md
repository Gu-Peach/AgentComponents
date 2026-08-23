# 3. SceneTransportSchema

`SceneTransportSchema` 是由 `DeviceSpec + SceneDocument` 编译出的场景级物料流转拓扑。

## 职责

- 将流程边、物理边和设备 transport behaviors 编译成可流转拓扑。
- 标记可用行为、不可编译连接和诊断信息。
- 为 `SimPlan` 和 `ExecutableSimGraph` 提供场景可执行能力边界。

## 输入与输出

| 项目 | 内容 |
|---|---|
| 上游输入 | DeviceSpec、SceneDocument。 |
| 输出 | transport nodes、transport edges、behavior bindings。 |
| 下游消费者 | Agent、SimPlan、ExecutableSimGraph、Runtime。 |

## Key 含义

### 通用元信息

| Key | 含义 |
|---|---|
| `schema_id` | 当前物料流转拓扑 schema 的唯一标识。 |
| `schema_type` | JSON 类型；示例使用 `SceneTransportSchema`。 |
| `version` | 规范版本。 |
| `name` | 拓扑名称。 |
| `description` | 拓扑用途说明。 |
| `source` | 编译来源，通常指向 `SceneDocument` 和相关 `DeviceSpec`。 |
| `created_for` | 该拓扑服务的场景或仿真目标。 |
| `references` | 引用的场景文档、设备本体或图片。 |
| `notes` | 派生规则和边界说明。 |

### 物料流转字段

| Key | 含义 |
|---|---|
| `scene_id` | 对应的场景 ID。 |
| `scene_revision` | 编译时使用的场景修订号。 |
| `transport_nodes` | 可参与物料流转的接口节点集合。 |
| `transport_edges` | 物料可从一个节点流向另一个节点的拓扑边。 |
| `behavior_bindings` | 场景连接关系激活的设备行为绑定。 |
| `diagnostics` | 编译诊断结果，如缺少接口绑定、方向不兼容。 |

### 常见嵌套字段

| Key | 含义 |
|---|---|
| `node_id` | transport node ID，通常为 `instance_id.interface_id`。 |
| `instance_id` | 节点所属设备实例。 |
| `interface_id` | 节点对应的物理接口。 |
| `material_classes` | 节点支持流转的物料类型。 |
| `edge_id` | transport edge ID。 |
| `from` | 流转起点节点。 |
| `to` | 流转终点节点。 |
| `process_edge` | 对应的工艺流程边。 |
| `physical_edge` | 对应的物理接口边。 |
| `required_signals` | 该流转边执行时依赖的信号。 |
| `binding_id` | 行为绑定 ID。 |
| `behavior_id` | 被激活的设备行为能力 ID。 |
| `input_interface` | 行为绑定使用的输入接口。 |
| `output_interface` | 行为绑定使用的输出接口。 |

### 规范辅助字段

| Key | 含义 |
|---|---|
| `required_sections` | `SceneTransportSchema` 必须包含的一级字段列表。 |
| `kind` | 来源类别，例如 `compiled_example` 或 `manual_design`。 |
| `compiled_from` | 编译该流转 schema 的上游场景事实。 |
