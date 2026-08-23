# 5. SimPlan

`SimPlan` 是 Agent 生成的本次仿真计划，描述目标、路线、设备选择、行为步骤、信号规则和成功条件。

## 职责

- 将用户意图转成结构化仿真计划。
- 选择要使用的设备实例和 transport behavior。
- 定义打断、暂停、失败和重规划策略。

## 输入与输出

| 项目 | 内容 |
|---|---|
| 上游输入 | 用户目标、DeviceSpec、SceneDocument、SceneTransportSchema、可选 RuntimeSnapshot。 |
| 输出 | 仿真计划。 |
| 下游消费者 | SignalBusSchema、ExecutableSimGraph、Runtime。 |

## Key 含义

### 通用元信息

| Key | 含义 |
|---|---|
| `schema_id` | 当前仿真计划的唯一标识。 |
| `schema_type` | JSON 类型；示例使用 `SimPlan`。 |
| `version` | 规范版本。 |
| `name` | 计划名称。 |
| `description` | 计划用途说明。 |
| `source` | 计划来源，通常是 Agent run 或人工示例。 |
| `created_for` | 该计划服务的用户目标或仿真目标。 |
| `references` | 引用的场景、拓扑和设备规范。 |
| `notes` | 计划边界、简化假设和注意事项。 |

### 计划字段

| Key | 含义 |
|---|---|
| `goal` | 用户目标或 Agent 解析后的仿真目标。 |
| `process_route` | 本次仿真采用的工艺流转路线。 |
| `selected_devices` | 本次计划选用的设备实例。 |
| `transport_steps` | 本次计划中的物料流转行为步骤。 |
| `signal_rules` | 本次计划需要的信号依赖或信号触发规则。 |
| `success_criteria` | 判断本次仿真成功的条件集合。 |
| `interrupt_policy` | 用户打断、死锁、超时等情况下的处理策略。 |

### 常见嵌套字段

| Key | 含义 |
|---|---|
| `step_id` | 计划步骤 ID。 |
| `instance_id` | 执行该步骤的设备实例。 |
| `behavior_id` | 该步骤使用的设备行为能力。 |
| `depends_on` | 当前步骤依赖的上游步骤。 |
| `trigger` | 当前步骤的启动信号或条件。 |
| `outputs` | 当前步骤完成或运行中输出的信号。 |
| `rule_id` | 信号规则 ID。 |
| `source` | 信号规则源端。 |
| `target` | 信号规则目标端。 |
| `on_user_interrupt` | 用户运行中修改/暂停时的策略。 |
| `on_deadlock` | 运行时检测到死锁时的策略。 |

### 规范辅助字段

| Key | 含义 |
|---|---|
| `required_sections` | `SimPlan` 必须包含的一级字段列表。 |
| `agent_run_id` | 生成该计划的 Agent run ID。 |
| `kind` | 来源类别，例如 `agent_example`、`manual_design`。 |
| `path` | 当前规范或示例文件路径。 |
