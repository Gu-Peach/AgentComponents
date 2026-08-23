# 6. ExecutableSimGraph

`ExecutableSimGraph` 是 Runtime 将 `SimPlan` 编译后的可执行图，直接服务 Scheduler。

## 职责

- 定义 action nodes、guards、effects、资源锁和失败策略。
- 将 Agent 计划落到 Runtime 可执行语义。
- 作为 `DeviceRuntimeProfile` 的计算依据。

## 输入与输出

| 项目 | 内容 |
|---|---|
| 上游输入 | SimPlan、SceneTransportSchema、SignalBusSchema。 |
| 输出 | 可执行动作图。 |
| 下游消费者 | Scheduler、RuntimeSnapshot、DeviceRuntimeProfile。 |

## Key 含义

### 通用元信息

| Key | 含义 |
|---|---|
| `schema_id` | 当前 Runtime 可执行图的唯一标识。 |
| `schema_type` | JSON 类型；示例使用 `ExecutableSimGraph`。 |
| `version` | 规范版本。 |
| `name` | 可执行图名称。 |
| `description` | 可执行图用途说明。 |
| `source` | 编译来源，通常指向 `SimPlan`。 |
| `created_for` | 该可执行图服务的 run 或计划目标。 |
| `references` | 引用的计划、信号 schema、流转 schema。 |
| `notes` | Runtime 表达式和调度边界说明。 |

### 可执行图字段

| Key | 含义 |
|---|---|
| `runtime_plan_id` | Runtime 计划 ID。 |
| `action_nodes` | 可执行动作节点列表。 |
| `dependencies` | 动作节点之间的依赖关系。 |
| `guards` | 动作启动前必须满足的条件。 |
| `effects` | 动作开始、完成或失败时产生的状态变化。 |
| `resource_locks` | 动作执行过程中需要占用的资源。 |
| `failure_handlers` | 失败或异常条件下的处理规则。 |
| `replan_triggers` | 触发 Agent 重规划或 Runtime 停止的条件。 |

### 常见嵌套字段

| Key | 含义 |
|---|---|
| `node_id` | 可执行动作节点 ID。 |
| `instance_id` | 动作所属设备实例。 |
| `behavior_id` | 动作对应的设备行为能力。 |
| `from` | 依赖关系的起点动作。 |
| `to` | 依赖关系的终点动作。 |
| `type` | 依赖类型，例如 `signal_dependency`。 |
| `signal` | 依赖的信号。 |
| `conditions` | guard 条件列表。 |
| `on_start` | 动作开始时执行的状态变化。 |
| `on_complete` | 动作完成时执行的状态变化。 |
| `condition` | 失败处理规则的触发条件。 |
| `handler` | 失败处理方式，例如 `emit_observation`。 |

### 规范辅助字段

| Key | 含义 |
|---|---|
| `required_sections` | `ExecutableSimGraph` 必须包含的一级字段列表。 |
| `compiled_from` | 编译该可执行图的上游计划。 |
| `kind` | 来源类别，例如 `compiled_example`、`manual_design`。 |
| `path` | 当前规范或示例文件路径。 |
