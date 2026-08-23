# 4. SignalBusSchema

`SignalBusSchema` 是信号通讯运行契约，由设备信号口、场景信号边和计划规则编译得到。

## 职责

- 定义 signal route、wait rule、payload schema 和 timeout rule。
- 为 Runtime SignalBus 提供普通信号传递规则。
- 只在异常、超时、死锁或用户打断时触发 Agent 介入。

## 输入与输出

| 项目 | 内容 |
|---|---|
| 上游输入 | DeviceSpec.signal_ports、SceneDocument.signal_edges、SimPlan.signal_rules。 |
| 输出 | 信号路由、等待规则、超时策略。 |
| 下游消费者 | SignalBus、RuntimeSnapshot、DeviceRuntimeProfile。 |

## Key 含义

### 通用元信息

| Key | 含义 |
|---|---|
| `schema_id` | 当前信号通讯 schema 的唯一标识。 |
| `schema_type` | JSON 类型；示例使用 `SignalBusSchema`。 |
| `version` | 规范版本。 |
| `name` | 信号通讯规范名称。 |
| `description` | 信号通讯用途说明。 |
| `source` | 编译来源，通常来自 `SceneDocument.signal_edges` 和 `SimPlan.signal_rules`。 |
| `created_for` | 该信号契约服务的运行目标。 |
| `references` | 引用的设备、场景、计划或规范。 |
| `notes` | 通讯边界和运行策略说明。 |

### 信号通讯字段

| Key | 含义 |
|---|---|
| `routes` | 信号从源端口到目标端口的路由规则。 |
| `wait_rules` | 等待规则，描述谁因为哪个状态等待、何时释放。 |
| `payload_schemas` | 信号 payload 的结构定义。 |
| `timeout_rules` | 信号等待或动作触发的超时策略。 |

### 常见嵌套字段

| Key | 含义 |
|---|---|
| `route_id` | 信号路由 ID。 |
| `source_signal` | 源信号，如 `conveyor_1.part_ready`。 |
| `target_signal` | 目标信号，如 `robot_1.start_pick`。 |
| `payload_schema` | 当前路由使用的 payload schema 名称。 |
| `delivery` | 投递语义，如 `at_least_once`。 |
| `rule_id` | 等待或超时规则 ID。 |
| `condition` | 进入等待或触发规则的条件表达式。 |
| `waiting_location` | 物料等待位置。 |
| `queue_id` | 等待队列 ID。 |
| `release_on` | 释放等待的信号或条件。 |
| `target` | 超时监控目标。 |
| `timeout_s` | 超时时间，单位秒。 |
| `on_timeout` | 超时后的处理策略，例如 `emit_observation`。 |

### 规范辅助字段

| Key | 含义 |
|---|---|
| `required_sections` | `SignalBusSchema` 必须包含的一级字段列表。 |
| `compiled_from` | 编译信号 schema 的上游场景或计划。 |
| `payload_material_event` | 示例中的物料事件 payload 定义名。 |
| `material_id` | 信号 payload 中携带的物料 ID。 |
| `source_instance_id` | 信号 payload 中的来源设备实例 ID。 |
| `timestamp` | 信号产生时间戳。 |
