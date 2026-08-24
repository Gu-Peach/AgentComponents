# ExecutableSimGraph 字段说明

本文用于解释 `6.ExecutableSimGraph/schema.json` 与 `example.json` 中每个板块和字段的含义。`ExecutableSimGraph` 是 Runtime 将 `SimPlan` 编译后的可执行动作图，直接面向 Scheduler 和设备 FSM。

## 1. schema 定位

`ExecutableSimGraph` 把 Agent 计划转成可执行语义。它不再是自然语言计划，而是动作节点、依赖、启动条件、效果、资源锁和失败处理组成的运行图。

```text
SimPlan + SceneTransportSchema + SignalBusSchema
  -> ExecutableSimGraph
  -> Scheduler / Runtime 执行
```

## 2. `schema.json` 规范字段

| 字段 | 含义 |
| --- | --- |
| `schema_id` | 当前规范文件 ID。 |
| `schema_type` | 当前规范类型，示例为 `ExecutableSimGraphSchemaContract`。 |
| `version` | 规范版本。 |
| `name` | 规范名称。 |
| `description` | 规范用途说明。 |
| `source.kind` | 规范来源类型。 |
| `source.path` | 规范文件路径。 |
| `created_for` | 服务目标，即 Runtime 调度执行。 |
| `references` | 依赖的通用规范、计划规范和信号规范。 |
| `notes` | 说明该结构面向调度器，不面向普通用户编辑。 |
| `required_sections` | 必须包含的一级字段。 |

## 3. 必填板块 `required_sections`

| 板块 | 含义 |
| --- | --- |
| `runtime_plan_id` | Runtime 可执行计划 ID。 |
| `action_nodes` | 可执行动作节点列表。 |
| `dependencies` | 动作节点之间的依赖关系。 |
| `guards` | 动作启动前的条件。 |
| `effects` | 动作开始、完成或失败时的状态变化。 |
| `resource_locks` | 执行动作需要占用的资源锁。 |
| `failure_handlers` | 失败处理规则。 |
| `replan_triggers` | 触发重规划的条件。 |

## 4. 示例元信息

| 字段 | 含义 |
| --- | --- |
| `schema_id` | 示例可执行图 ID。 |
| `schema_type` | 示例类型，实际可执行图使用 `ExecutableSimGraph`。 |
| `source.kind` | 来源类型，`compiled_example` 表示编译示例。 |
| `source.compiled_from` | 编译来源计划。 |
| `references` | 引用的流转拓扑、信号 schema 和计划。 |
| `notes` | 示例表达式格式说明。 |

## 5. Runtime 计划 ID `runtime_plan_id`

| 字段 | 含义 |
| --- | --- |
| `runtime_plan_id` | 可执行图在 Runtime 中的唯一 ID。 |

该 ID 可用于启动 simulation run、关联快照、恢复执行和审计事件。

## 6. 动作节点 `action_nodes`

| 字段 | 含义 |
| --- | --- |
| `node_id` | 动作节点 ID。 |
| `instance_id` | 执行动作的设备实例。 |
| `behavior_id` | 对应设备本体中的行为 ID。 |

`action_nodes` 是 Scheduler 可以派发的最小动作单元。

## 7. 依赖关系 `dependencies`

| 字段 | 含义 |
| --- | --- |
| `from` | 上游动作节点。 |
| `to` | 下游动作节点。 |
| `type` | 依赖类型，例如 `signal_dependency`。 |
| `signal` | 依赖的信号。 |

示例中机械臂抓取依赖传送带输出 `conveyor_1.part_ready`。

## 8. 启动条件 `guards`

| 字段 | 含义 |
| --- | --- |
| `node_id` | guard 所属动作节点。 |
| `conditions` | 该动作启动前必须满足的条件表达式列表。 |

guard 可检查设备 FSM、物料位置、资源锁、信号值等运行条件。

## 9. 执行效果 `effects`

| 字段 | 含义 |
| --- | --- |
| `node_id` | effect 所属动作节点。 |
| `on_start` | 动作开始时产生的状态变化。 |
| `on_complete` | 动作完成时产生的状态变化。 |

示例中机械臂动作开始时设置 `busy` 并锁定夹爪；完成时发出 `done`、移动物料并释放夹爪。

## 10. 资源锁 `resource_locks`

| 字段 | 含义 |
| --- | --- |
| `resource_locks` | 可执行图涉及的资源锁列表。 |

资源锁用于避免同一设备资源被多个动作同时占用，例如 `robot_1.gripper`。
意思是：只有 robot_1 的夹爪当前没有被占用，才能执行这个 pick 动作。

## 11. 失败处理 `failure_handlers`

| 字段 | 含义 |
| --- | --- |
| `condition` | 失败处理触发条件。 |
| `handler` | 处理方式，如 `emit_observation`。 |

`emit_observation` 表示 Runtime 把异常观察发送给 Agent 或诊断模块，由上层决定是否重规划。

## 12. 重规划触发 `replan_triggers`

| 字段 | 含义 |
| --- | --- |
| `replan_triggers` | 触发重规划或暂停执行的事件列表。 |

常见触发包括 `deadlock_detected`、`user_interrupt`、`timeout`。

## 13. 下游使用方式

```text
Scheduler 读取 action_nodes / dependencies
  -> 决定动作派发顺序

Runtime 读取 guards / resource_locks
  -> 判断动作是否能执行

Runtime 执行 effects
  -> 更新 RuntimeSnapshot

DeviceRuntimeProfile 基于图和快照
  -> 计算每个设备当前可执行、等待、阻塞的行为
```

