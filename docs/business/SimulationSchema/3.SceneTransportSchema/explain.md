# SceneTransportSchema 字段说明

本文用于解释 `3.SceneTransportSchema/schema.json` 与 `example.json` 中每个板块和字段的含义。`SceneTransportSchema` 是由 `DeviceSpec + SceneDocument` 编译出的场景级物料流转拓扑。

## 1. schema 定位

`SceneTransportSchema` 不是人工长期维护的第一事实，而是派生 schema。它把场景中的流程边、物理边和设备行为能力编译成 Runtime 与 Agent 可理解的物料流转拓扑。

```text
DeviceSpec.transport_behaviors
  + SceneDocument.process_edges / physical_edges
  -> SceneTransportSchema.transport_nodes / transport_edges / behavior_bindings
```

## 2. `schema.json` 规范字段

| 字段 | 含义 |
| --- | --- |
| `schema_id` | 当前规范文件 ID。 |
| `schema_type` | 当前规范类型，示例为 `SceneTransportSchemaContract`。 |
| `version` | 规范版本。 |
| `name` | 规范名称。 |
| `description` | 规范用途说明。 |
| `source.kind` | 规范来源类型。 |
| `source.path` | 规范文件路径。 |
| `created_for` | 服务目标，即场景级 transport 拓扑编译。 |
| `references` | 依赖的通用规范和场景事实规范。 |
| `notes` | 说明该 schema 是派生结果，必须可从上游重建。 |
| `required_sections` | 必须包含的一级字段。 |

## 3. 必填板块 `required_sections`

| 板块 | 含义 |
| --- | --- |
| `scene_id` | 对应场景 ID。 |
| `scene_revision` | 编译时使用的场景修订号。 |
| `transport_nodes` | 可参与物料流转的节点集合。 |
| `transport_edges` | 物料可流动的拓扑边集合。 |
| `behavior_bindings` | 场景连接激活的设备行为绑定。 |
| `diagnostics` | 编译诊断信息。 |

## 4. 示例元信息

| 字段 | 含义 |
| --- | --- |
| `schema_id` | 示例 ID。 |
| `schema_type` | 示例类型，实际派生结果使用 `SceneTransportSchema`。 |
| `source.kind` | 示例来源，`compiled_example` 表示编译示例。 |
| `source.compiled_from` | 编译来源，通常指向 `SceneDocument`。 |
| `references` | 示例引用的场景文档和设备本体。 |
| `notes` | 示例补充说明。 |

## 5. 流转节点 `transport_nodes`

`transport_nodes` 是物料流转图中的节点，通常对应某个设备实例的物理接口。描述物料可能出现、进入、离开、被抓取、被放置的位置节点

| 字段 | 含义 |
| --- | --- |
| `node_id` | 流转节点 ID，常用格式为 `instance_id.interface_id`。 |
| `instance_id` | 节点所属设备实例。 |
| `interface_id` | 节点对应的物理接口。 |
| `material_classes` | 节点支持流转的物料类别。 |

## 6. 流转边 `transport_edges`

`transport_edges` 描述物料可从哪个节点流向哪个节点，以及该流转依赖哪些场景边和信号。

| 字段 | 含义 |
| --- | --- |
| `edge_id` | 流转边 ID。 |
| `from` | 起点 transport node。 |
| `to` | 终点 transport node。 |
| `process_edge` | 对应的工艺流程边 ID。 |
| `physical_edge` | 对应的物理接口边 ID。 |
| `required_signals` | 执行该流转所需或相关的信号。 |

## 7. 行为绑定 `behavior_bindings`

`behavior_bindings` 说明某个场景连接激活了某个设备实例上的哪个行为能力。

| 字段 | 含义 |
| --- | --- |
| `binding_id` | 行为绑定 ID。 |
| `instance_id` | 设备实例 ID。 |
| `behavior_id` | 被激活的设备行为 ID。 |
| `input_interface` | 行为输入接口，可选。 |
| `output_interface` | 行为输出接口，可选。 |

例如传送带连接到机械臂时，可能激活传送带的 `transport_to_exit` 和机械臂的 `pick_and_place`。

## 8. 诊断结果 `diagnostics`

| 字段 | 含义 |
| --- | --- |
| `diagnostics` | 编译诊断列表。空数组表示当前示例未发现错误或警告。 |

后续可在其中记录缺少接口绑定、物料类型不兼容、方向冲突、信号缺失等问题。

## 9. 下游使用方式

```text
Agent 读取 SceneTransportSchema
  -> 判断当前场景有哪些可用路线和行为能力

SimPlan 引用 transport_edges / behavior_bindings
  -> 生成本次仿真路线和步骤

ExecutableSimGraph 继续编译
  -> 形成 action_nodes、guards、effects 和资源锁
```

