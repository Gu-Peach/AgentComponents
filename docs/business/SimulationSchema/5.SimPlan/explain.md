# SimPlan 字段说明

本文用于解释 `5.SimPlan/schema.json` 与 `example.json` 中每个板块和字段的含义。`SimPlan` 是 Agent 生成的结构化仿真计划，描述本次仿真的目标、路线、设备选择、行为步骤、信号规则、成功条件和打断策略。

## 1. schema 定位

`SimPlan` 位于 Agent 决策层，不直接驱动设备执行。Runtime 需要继续把它编译成 `ExecutableSimGraph`，再由调度器执行。

```text
用户目标 + SceneDocument + SceneTransportSchema + 可选 RuntimeSnapshot
  -> Agent 生成 SimPlan
  -> Runtime 编译 ExecutableSimGraph
```

## 2. `schema.json` 规范字段

| 字段 | 含义 |
| --- | --- |
| `schema_id` | 当前规范文件 ID。 |
| `schema_type` | 当前规范类型，示例为 `SimPlanSchemaContract`。 |
| `version` | 规范版本。 |
| `name` | 规范名称。 |
| `description` | 规范用途说明。 |
| `source.kind` | 规范来源类型。 |
| `source.path` | 规范文件路径。 |
| `created_for` | 服务目标，即 Agent 计划生成。 |
| `references` | 依赖的通用规范和场景流转规范。 |
| `notes` | 说明 `SimPlan` 不直接驱动设备。 |
| `required_sections` | 必须包含的一级字段。 |

## 3. 必填板块 `required_sections`

| 板块 | 含义 |
| --- | --- |
| `goal` | 本次仿真的目标。 |
| `process_route` | 工艺路线。 |
| `selected_devices` | 本次计划选用的设备实例。 |
| `transport_steps` | 行为步骤列表。 |
| `signal_rules` | 信号依赖和触发规则。 |
| `success_criteria` | 成功条件。 |
| `interrupt_policy` | 用户打断、死锁、异常时的处理策略。 |

## 4. 示例元信息

| 字段 | 含义 |
| --- | --- |
| `schema_id` | 示例计划 ID。 |
| `schema_type` | 示例类型，实际计划使用 `SimPlan`。 |
| `source.kind` | 计划来源，`agent_example` 表示 Agent 示例输出。 |
| `source.agent_run_id` | 生成该计划的 Agent run ID。 |
| `references` | 计划引用的场景文档和流转拓扑。 |
| `notes` | 示例边界说明。 |

## 5. 仿真目标 `goal`

| 字段 | 含义 |
| --- | --- |
| `goal` | 用户目标经 Agent 解析后的结构化目标描述。 |

示例中的目标是将 `part_001` 从 `conveyor_1.exit` 移动到 `robot_1.pick_area`。

## 6. 工艺路线 `process_route`

| 字段 | 含义 |
| --- | --- |
| `process_route` | 本次计划采用的设备实例顺序。 |

`process_route` 是计划层路线，不等于运行时动作图。它描述本次仿真的主工艺路径。

## 7. 设备选择 `selected_devices`

| 字段 | 含义 |
| --- | --- |
| `selected_devices` | Agent 为本次目标选择的设备实例列表。 |

该字段限定后续 `transport_steps`、`signal_rules` 和执行图编译的设备范围。

## 8. 行为步骤 `transport_steps`

`transport_steps` 是计划中的核心步骤列表，每个步骤引用某个设备实例的行为能力。

| 字段 | 含义 |
| --- | --- |
| `step_id` | 步骤 ID。 |
| `instance_id` | 执行该步骤的设备实例。 |
| `behavior_id` | 使用的设备行为 ID，来自对应 `DeviceSpec.transport_behaviors`。 |
| `depends_on` | 当前步骤依赖的上游步骤。 |
| `trigger` | 当前步骤的启动信号或条件。 |
| `outputs` | 步骤执行过程中或完成后输出的信号。 |

示例中传送带先执行 `transport_to_exit`，输出 `conveyor_1.part_ready`，再触发机械臂 `pick_and_place`。

## 9. 信号规则 `signal_rules`

| 字段 | 含义 |
| --- | --- |
| `rule_id` | 信号规则 ID。 |
| `source` | 源信号端口。 |
| `target` | 目标信号端口。 |

`signal_rules` 会参与编译 `SignalBusSchema.routes`，用于描述计划中必须建立的运行时通讯关系。

## 10. 成功条件 `success_criteria`

| 字段 | 含义 |
| --- | --- |
| `success_criteria` | 判断本次计划是否完成的条件表达式列表。 |

示例中同时要求物料到达目标位置，并且机械臂 `done` 为 true。

## 11. 打断策略 `interrupt_policy`

| 字段 | 含义 |
| --- | --- |
| `on_user_interrupt` | 用户运行中修改、暂停或改变目标时的策略。 |
| `on_deadlock` | 死锁发生时的策略。 |

示例中的 `pause_and_replan_remaining` 表示先暂停仿真，再基于当前 `RuntimeSnapshot` 重规划剩余动作。

## 12. 下游使用方式

```text
SignalBusSchema 读取 signal_rules
  -> 编译信号路由和等待规则

ExecutableSimGraph 读取 transport_steps / success_criteria / interrupt_policy
  -> 编译 action_nodes、dependencies、guards、effects 和 replan_triggers

Runtime 执行后生成 RuntimeSnapshot
  -> 用于恢复、诊断和运行中重规划
```

