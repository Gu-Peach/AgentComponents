# SignalBusSchema 字段说明

本文用于解释 `4.SignalBusSchema/schema.json` 与 `example.json` 中每个板块和字段的含义。`SignalBusSchema` 是运行时信号通讯契约，描述信号如何路由、等待、携带 payload 和超时处理。

## 1. schema 定位

`SignalBusSchema` 由设备信号口、场景信号边和计划信号规则编译得到。它服务 Runtime 的 SignalBus，不由 LLM 在普通信号流转中实时管理。

```text
DeviceSpec.signal_ports
  + SceneDocument.signal_edges
  + SimPlan.signal_rules
  -> SignalBusSchema.routes / wait_rules / timeout_rules
```

## 2. `schema.json` 规范字段

| 字段 | 含义 |
| --- | --- |
| `schema_id` | 当前规范文件 ID。 |
| `schema_type` | 当前规范类型，示例为 `SignalBusSchemaContract`。 |
| `version` | 规范版本。 |
| `name` | 规范名称。 |
| `description` | 规范用途说明。 |
| `source.kind` | 规范来源类型。 |
| `source.path` | 规范文件路径。 |
| `created_for` | 服务目标，即实时信号通讯和设备 FSM 协调。 |
| `references` | 依赖的通用规范、场景规范和计划规范。 |
| `notes` | 说明该 schema 是派生 schema。 |
| `required_sections` | 必须包含的一级字段。 |

## 3. 必填板块 `required_sections`

| 板块 | 含义 |
| --- | --- |
| `routes` | 信号路由规则。 |
| `wait_rules` | 等待规则。 |
| `payload_schemas` | 信号 payload 结构定义。 |
| `timeout_rules` | 超时规则。 |

## 4. 示例元信息

| 字段 | 含义 |
| --- | --- |
| `schema_id` | 示例 ID。 |
| `schema_type` | 示例类型，实际通讯契约使用 `SignalBusSchema`。 |
| `source.kind` | 示例来源，`compiled_example` 表示编译示例。 |
| `source.compiled_from` | 编译来源，可同时来自场景和计划。 |
| `references` | 示例引用的设备本体。 |
| `notes` | 运行边界说明，例如普通信号流转不调用 LLM。 |

## 5. 信号路由 `routes`

`routes` 描述一个源信号如何投递到目标信号端口。

| 字段 | 含义 |
| --- | --- |
| `route_id` | 路由 ID。 |
| `source_signal` | 源信号，格式通常为 `instance_id.signal_port`。 |
| `target_signal` | 目标信号。 |
| `payload_schema` | 该路由使用的 payload schema 名称。 |
| `delivery` | 投递语义，如 `at_least_once`。 |

## 6. 等待规则 `wait_rules`

`wait_rules` 描述运行时因某个状态或条件导致物料、动作或设备等待的规则。

| 字段 | 含义 |
| --- | --- |
| `rule_id` | 等待规则 ID。 |
| `condition` | 进入等待的条件表达式。 |
| `waiting_location` | 等待发生的位置，例如某设备出口。 |
| `queue_id` | 等待队列 ID。 |
| `release_on` | 释放等待的信号或条件。 |

示例中 `robot_1.busy == true` 时，物料在 `conveyor_1.exit` 等待，直到 `robot_1.done` 释放。

## 7. Payload 结构 `payload_schemas`

`payload_schemas` 定义信号携带的数据结构。

| 字段 | 含义 |
| --- | --- |
| `payload_material_event` | 示例中的物料事件 payload 名称。 |
| `material_id` | 物料实例 ID。 |
| `source_instance_id` | 信号来源设备实例 ID。 |
| `timestamp` | 信号产生时间戳。 |

## 8. 超时规则 `timeout_rules`

`timeout_rules` 描述目标信号或动作长时间未发生时如何处理。

| 字段 | 含义 |
| --- | --- |
| `rule_id` | 超时规则 ID。 |
| `target` | 被监控的信号或动作。 |
| `timeout_s` | 超时时间，单位秒。 |
| `on_timeout` | 超时后的处理方式，如 `emit_observation`。 |

## 9. 下游使用方式

```text
SignalBus 读取 routes
  -> 投递 signal_event

Runtime 读取 wait_rules
  -> 维护等待队列和释放条件

Runtime 读取 timeout_rules
  -> 超时后生成 observation，必要时交给 Agent 重规划

RuntimeSnapshot 记录 signal_values / wait_queues
  -> 反映当前信号和值状态
```

