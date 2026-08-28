# 4. SceneBehaviorGraph

`SceneBehaviorGraph` 是当前 v0.2 基线中的核心 Agent 行为建模结果。

它描述的是：**在给定 `DeviceSpec`、`SceneDocument` 和用户目标后，这个场景实际应该如何运行。**

---

## 职责

- 将用户目标转成场景级运行模块、事件总线、状态变量、行为规则和策略函数。
- 描述设备之间如何通过事件和状态协作，而不是只保存静态约束。
- 为 Simulation Runtime 的 Scheduler、SignalBusRuntime、ActionExecutor 和 SnapshotManager 提供运行依据。
- 替代旧拆分链路中的多个中间产物，作为当前唯一持久化场景行为建模结果。

---

## 输入与输出

| 项目 | 内容 |
|---|---|
| 上游输入 | DeviceSpec、SceneDocument、用户目标。 |
| 输出 | SceneBehaviorGraph。 |
| 下游消费者 | Simulation Runtime、Scheduler、SignalBusRuntime、SnapshotManager、前端解释面板。 |

Agent 节点、工具、上下文管理、Runtime 调度和存储方案见 `../../../design/agent_scene_behavior_graph_design.md`。

---

## 核心结构

| 板块 | 含义 |
|---|---|
| `goal` | 用户目标、场景假设和本次行为建模边界。 |
| `modules` | 场景流水线模块，可顺序、并行或持续运行。 |
| `event_bus` | 本场景实际启用的设备事件、全局事件、控制事件和路由规则。 |
| `state_model` | RuntimeSnapshot 需要维护的状态变量定义。 |
| `behavior_rules` | 事件 + 状态条件如何触发设备行为。 |
| `state_transition_rules` | 行为开始、完成、异常时如何修改 RuntimeSnapshot。 |
| `policies` | 动态策略函数，如共享工件池 claim、backpressure、容量阈值。 |
| `completion_conditions` | 场景完成条件。 |
| `failure_observations` | 异常、死锁、超载、资源冲突等观测事件。 |

`event_bus` 的事件注册模板、`kind` 枚举、`payload_schema`、`routes.delivery` 和 `to.type` 详细说明见 [`event_bus/event_bus.md`](event_bus/event_bus.md)。

---

## `behavior_rules` 规则结构

`behavior_rules` 是 Scheduler 直接解释的规则集合。每条规则必须显式区分四层：

| 字段 | 含义 | 产生阶段 |
|---|---|---|
| `trigger` | 规则何时被唤醒，例如事件到达、状态变化、scheduler tick。 | Agent 的 `EventStateModelerNode` / `BehaviorRuleNode` 生成。 |
| `guard` | 唤醒后是否允许执行，例如设备空闲、工件池非空、资源未锁、传送带未 blocked。 | Agent 的 `BehaviorRuleNode` 生成。 |
| `policy` | 多候选或动态选择时如何决策，例如共享工件池 claim、负载均衡、确定性优先级。 | Agent 的 `PolicySynthesizerNode` 生成，引用 `policies`。 |
| `action` | 条件满足后的执行结果，例如启动设备行为、投递事件、继续行为或更新状态。 | Agent 的 `BehaviorRuleNode` 生成。 |

推荐结构：

```json
{
  "rule_id": "robot_claim_and_pick",
  "module_id": "parallel_robot_sorting",
  "trigger": { "type": "event", "event_id": "robot.pick_request" },
  "guard": {
    "all": [
      "workpiece_pool.pallet_1.remaining_parts.empty == false",
      "device_states[trigger.payload.robot_id] == idle"
    ]
  },
  "policy": {
    "policy_id": "claim_workpiece",
    "inputs": { "robot_id": "trigger.payload.robot_id" },
    "bind_outputs_to": { "material_id": "action.payload.material_id" }
  },
  "action": {
    "type": "start_behavior",
    "instance_id": "trigger.payload.robot_id",
    "behavior_id": "pick_and_place",
    "payload": { "material_id": "policy.material_id" }
  }
}
```

旧写法 `when_event` / `when_state` / `if` / `then_*` 只作为历史简写理解；当前模板和案例统一使用 `trigger / guard / policy / action`。

---

## `event_bus.routes` 路由结构

`event_bus.routes` 表达的是 **事件到消费者** 的投递规则，不是“事件到事件”的转换规则。

`event_bus.events` 负责注册事件和 payload 契约；`event_bus.routes` 负责描述事件发生后的消费者；Runtime 内部的 `SignalBusRuntime` 负责按这些定义执行实际投递。完整字段模板见 [`event_bus/event_bus.md`](event_bus/event_bus.md)。

推荐结构：

```json
{
  "route_id": "route_sim_start_to_start_pallet_transport_rule",
  "from": "runtime.sim_start",
  "to": {
    "type": "rule",
    "id": "start_pallet_transport"
  },
  "delivery": "direct"
}
```

字段含义：

| 字段 | 含义 |
|---|---|
| `from` | 已发生的事件 ID。 |
| `to.type` | 消费者类型，可为 `rule`、`topic`、`module`、`device`、`runtime`。 |
| `to.id` | 消费者 ID，例如 rule_id、topic_id 或 Runtime 内部模块名。 |
| `delivery` | 投递方式，例如 `direct`、`broadcast`、`internal`。 |
| `target_resolver` | 可选，描述如何从 payload、binding 或 subscription 中解析具体目标。 |

第一阶段建议优先支持：

```text
rule
  事件直接唤醒某条 behavior_rule。

topic
  事件广播到某个主题，多条 rule 或 observer 可订阅。
```

`module`、`device`、`runtime` 可作为后续扩展目标类型。

---

## `policy` 策略说明

`policy` 是 Scheduler 在 `guard` 通过之后调用的动态决策步骤。

它不直接保存可执行代码，而是保存：

```text
policy_id
  引用 SceneBehaviorGraph.policies 中定义的策略。

inputs
  传给策略函数的参数，可以来自 trigger.payload、RuntimeSnapshot、state_model 或常量。

bind_outputs_to
  把策略计算结果绑定到 action、payload、target 或状态路径中。
```

Runtime 中真正执行策略的是 `PolicyLibrary`：

```text
SceneBehaviorGraph.policies
  定义策略类型和参数。

Runtime PolicyLibrary
  执行策略逻辑。

behavior_rules[].policy
  在某条规则里引用策略，并声明输入和输出绑定。
```

完整策略案例和执行流程见 [`case.md`](case.md)。当前模板覆盖：

| policy type | 作用 |
|---|---|
| `deterministic_priority` | 保证单线程 DES 中同一时刻多规则执行顺序稳定。 |
| `shared_pool_claim` | 多设备从共享工件池原子领取任务，避免重复 claim。 |
| `load_balancing` | 在多个候选目标中选择未 blocked 且负载更低的目标。 |
| `capacity_threshold` | 基于容量阈值实现 backpressure。 |
| `resource_lock` | 行为启动前申请设备或物料互斥资源。 |
| `queue_wait` | 当前不可执行但非异常时进入等待队列。 |
| `deadlock_detection` | 无可执行规则且任务未完成时产生异常观测。 |
| `timeout_retry` | 动作或等待超时后的重试与失败观测。 |

---

## 与 RuntimeSnapshot 的边界

```text
SceneBehaviorGraph
  定义“应该如何运行”。

RuntimeSnapshot
  保存“现在运行到什么状态”。
```

运行时，Scheduler 读取 `SceneBehaviorGraph + RuntimeSnapshot` 决定下一步行为；SignalBusRuntime 按 `event_bus.routes` 传递事件；SnapshotManager 按 `state_transition_rules` 更新 RuntimeSnapshot。
