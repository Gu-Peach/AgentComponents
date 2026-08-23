# DeviceRuntimeProfile 字段说明

本文用于解释 `8.DeviceRuntimeProfile/schema.json` 与 `example.json` 中每个板块和字段的含义。`DeviceRuntimeProfile` 是由 `ExecutableSimGraph + RuntimeSnapshot` 实时计算出的单设备行为画像。

## 1. schema 定位

`DeviceRuntimeProfile` 是动态视图，不是设备本体数据，也不是场景事实。它回答“某个设备此刻能做什么、在等什么、被什么阻塞、正在执行什么”。

```text
ExecutableSimGraph  给出可执行动作、依赖、guards、effects
RuntimeSnapshot      给出当前信号、状态、物料位置和资源锁
  -> DeviceRuntimeProfile
  -> Scheduler / 前端 / Agent observation
```

## 2. `schema.json` 规范字段

| 字段 | 含义 |
| --- | --- |
| `schema_id` | 当前规范文件 ID。 |
| `schema_type` | 当前规范类型，示例为 `DeviceRuntimeProfileSchemaContract`。 |
| `version` | 规范版本。 |
| `name` | 规范名称。 |
| `description` | 规范用途说明。 |
| `source.kind` | 规范来源类型。 |
| `source.path` | 规范文件路径。 |
| `created_for` | 服务目标，即设备运行时行为画像计算。 |
| `references` | 依赖的通用规范、可执行图和运行时快照。 |
| `notes` | 说明该结构是动态视图。 |
| `required_sections` | 必须包含的一级字段。 |

## 3. 必填板块 `required_sections`

| 板块 | 含义 |
| --- | --- |
| `run_id` | 当前仿真运行 ID。 |
| `device_instance_id` | 当前画像描述的设备实例 ID。 |
| `current_state` | 设备当前 FSM 状态。 |
| `enabled_behaviors` | 当前可以执行的行为集合。 |
| `waiting_behaviors` | 当前等待信号、物料或资源的行为集合。 |
| `blocked_behaviors` | 当前被阻塞的行为集合。 |
| `executing_behavior` | 当前正在执行的行为。 |
| `next_events` | 下一步可能产生的事件或信号。 |

## 4. 示例元信息

| 字段 | 含义 |
| --- | --- |
| `schema_id` | 示例画像 ID。 |
| `schema_type` | 示例类型，实际画像使用 `DeviceRuntimeProfile`。 |
| `source.kind` | 来源类型，`computed_example` 表示计算示例。 |
| `source.from` | 计算该画像所依据的上游结构。 |
| `references` | 引用的设备本体。 |
| `notes` | 说明 Scheduler 消费结构化行为集合。 |

## 5. 运行 ID `run_id`

| 字段 | 含义 |
| --- | --- |
| `run_id` | 当前画像所属仿真运行 ID。 |

## 6. 设备实例 `device_instance_id`

| 字段 | 含义 |
| --- | --- |
| `device_instance_id` | 当前画像描述的单个设备实例。 |

每个设备实例通常可以计算出一个独立的 `DeviceRuntimeProfile`。

## 7. 当前状态 `current_state`

| 字段 | 含义 |
| --- | --- |
| `current_state` | 设备当前 FSM 状态，来自 `RuntimeSnapshot.device_fsm_states`。 |

该状态必须与对应设备本体 `runtime_contract.fsm_states` 兼容。

## 8. 可执行行为 `enabled_behaviors`

`enabled_behaviors` 表示当前所有条件已满足、Scheduler 可以考虑派发的行为。

| 字段 | 含义 |
| --- | --- |
| `behavior_id` | 可执行行为 ID。 |
| `action_node` | 对应的 `ExecutableSimGraph.action_nodes[].node_id`。 |
| `reason` | 行为可执行的原因说明。 |

示例中 `pick_and_place` 可执行，是因为 `part_ready` 已满足且夹爪资源可用。

## 9. 等待行为 `waiting_behaviors`

`waiting_behaviors` 表示当前还不能执行，但不是错误，只是在等待某个信号、物料、资源或时间条件。

| 字段 | 含义 |
| --- | --- |
| `behavior_id` | 等待中的行为 ID。 |
| `action_node` | 对应动作节点。 |
| `reason` | 等待原因。 |

常见等待原因包括下游 busy、物料未到位、目标信号未触发、队列未释放。

## 10. 阻塞行为 `blocked_behaviors`

`blocked_behaviors` 表示当前因为资源冲突、容量满、死锁、异常或不可达条件导致无法推进的行为。

| 字段 | 含义 |
| --- | --- |
| `behavior_id` | 被阻塞的行为 ID。 |
| `action_node` | 对应动作节点。 |
| `reason` | 阻塞原因。 |

阻塞行为通常会进入诊断或重规划判断。

## 11. 正在执行行为 `executing_behavior`

| 字段 | 含义 |
| --- | --- |
| `executing_behavior` | 当前设备正在执行的行为；无执行行为时为 `null`。 |

后续可扩展为对象，记录动作 ID、开始时间、预计完成时间、进度和占用资源。

## 12. 下一步事件 `next_events`

| 字段 | 含义 |
| --- | --- |
| `next_events` | 如果继续执行当前可执行或正在执行的行为，可能产生的信号或事件。 |

示例中的 `robot_1.busy` 和 `robot_1.done` 分别表示机械臂动作开始和完成时的信号变化。

## 13. 下游使用方式

```text
Scheduler 读取 enabled_behaviors
  -> 派发下一步动作

Runtime / UI 读取 waiting_behaviors / blocked_behaviors
  -> 展示等待和阻塞原因

Agent 在异常或用户打断时读取 DeviceRuntimeProfile
  -> 判断剩余计划是否需要修改

WebSocket/SSE 事件层读取 next_events
  -> 给前端展示设备下一步状态变化
```

