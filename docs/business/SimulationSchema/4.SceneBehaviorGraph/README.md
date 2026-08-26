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

Agent 节点、工具、上下文管理、Runtime 调度和存储方案见 `../agent_scene_behavior_graph_design.md`。

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

---

## 与 RuntimeSnapshot 的边界

```text
SceneBehaviorGraph
  定义“应该如何运行”。

RuntimeSnapshot
  保存“现在运行到什么状态”。
```

运行时，Scheduler 读取 `SceneBehaviorGraph + RuntimeSnapshot` 决定下一步行为；SignalBusRuntime 按 `event_bus.routes` 传递事件；SnapshotManager 按 `state_transition_rules` 更新 RuntimeSnapshot。
