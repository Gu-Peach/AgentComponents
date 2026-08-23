# 8. DeviceRuntimeProfile

`DeviceRuntimeProfile` 是设备当前行为画像，由 `ExecutableSimGraph + RuntimeSnapshot` 实时计算。

## 职责

- 描述某个设备实例当前 enabled、waiting、blocked、executing 的行为集合。
- 为 Scheduler 判断下一步可执行动作提供输入。
- 为前端展示设备状态提供结构化视图。

## 输入与输出

| 项目 | 内容 |
|---|---|
| 上游输入 | ExecutableSimGraph、RuntimeSnapshot。 |
| 输出 | 单设备当前行为画像。 |
| 下游消费者 | Scheduler、WebSocket/SSE 前端事件、Agent observation。 |

## Key 含义

### 通用元信息

| Key | 含义 |
|---|---|
| `schema_id` | 当前设备运行画像示例的唯一标识。 |
| `schema_type` | JSON 类型；示例使用 `DeviceRuntimeProfile`。 |
| `version` | 规范版本。 |
| `name` | 运行画像名称。 |
| `description` | 运行画像用途说明。 |
| `source` | 画像来源，通常由 Runtime 根据图和快照计算。 |
| `created_for` | 该画像服务的调度、前端展示或 Agent observation 目标。 |
| `references` | 引用的设备本体、可执行图和运行时快照。 |
| `notes` | 动态视图边界和调度说明。 |

### 设备运行画像字段

| Key | 含义 |
|---|---|
| `run_id` | 当前仿真运行 ID。 |
| `device_instance_id` | 被描述的设备实例 ID。 |
| `current_state` | 设备当前 FSM 状态。 |
| `enabled_behaviors` | 当前条件已满足、可以执行的行为集合。 |
| `waiting_behaviors` | 当前正在等待信号、物料或资源的行为集合。 |
| `blocked_behaviors` | 当前被资源、下游容量或异常阻塞的行为集合。 |
| `executing_behavior` | 当前正在执行的行为；没有则为 `null`。 |
| `next_events` | 如果执行当前行为，下一步可能产生的信号或事件。 |

### 常见嵌套字段

| Key | 含义 |
|---|---|
| `behavior_id` | 设备行为能力 ID。 |
| `action_node` | 对应的 `ExecutableSimGraph.action_nodes[].node_id`。 |
| `reason` | 行为为什么可执行、等待或阻塞的解释。 |

### 规范辅助字段

| Key | 含义 |
|---|---|
| `required_sections` | `DeviceRuntimeProfile` 必须包含的一级字段列表。 |
| `kind` | 来源类别，例如 `computed_example`、`manual_design`。 |
| `from` | 计算该画像所依据的上游结构列表。 |
| `path` | 当前规范或示例文件路径。 |
