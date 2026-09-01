# SceneBehaviorGraph.event_bus 说明

`event_bus` 是 `SceneBehaviorGraph` 中描述**场景事件、设备信号、控制消息和事件投递关系**的板块。

它不是独立运行时组件，也不是单独 schema。运行时由 `SignalBusRuntime` 读取 `event_bus.events` 和 `event_bus.routes`，完成事件校验、路由匹配和投递。

---

## 1. 职责边界

| 对象 | 职责 |
|---|---|
| `event_bus.events` | 注册本场景所有可能出现的事件和信号，定义事件 ID、类型、来源和 payload 结构。 |
| `event_bus.topics` | 定义广播主题。topic 是逻辑通道，不是事件，也不是行为规则。 |
| `event_bus.subscriptions` | 定义每个 topic 的消费者，例如哪些 rule、module、device 或 Runtime 内部模块订阅该 topic。 |
| `event_bus.routes` | 定义事件发生后应该投递给谁，例如某条规则、某个 topic、某个 Runtime 内部模块。 |
| `SignalBusRuntime` | Runtime 内部模块，按 `event_bus` 执行事件校验、路由匹配、投递和事件日志写入。 |
| `RuntimeSnapshot.signal_values` | 保存信号或事件的最新值、队列状态、消费状态等运行时事实，不负责定义事件规则。 |

一句话：`event_bus` 定义“事件和信号应该怎么流动”，`SignalBusRuntime` 执行“实际投递”，`RuntimeSnapshot` 记录“当前流动到什么状态”。

---

## 2. `events` 标准模板

```json
{
  "event_id": "runtime.sim_start",
  "kind": "global_event",
  "source": "runtime",
  "description": "仿真启动事件，用于唤醒第一阶段行为规则。",
  "payload_schema": {},
  "retention": "event_log"
}
```

### 字段含义

| 字段 | 是否必填 | 含义 |
|---|---:|---|
| `event_id` | 是 | 事件唯一 ID，建议使用命名空间形式，如 `runtime.sim_start`、`main_conveyor_1.pallet_ready`、`conveyor.blocked`。 |
| `kind` | 是 | 事件类型，用来区分全局事件、设备信号、控制事件和异常观测。 |
| `source` | 建议 | 事件默认来源，可以是设备实例 ID、`runtime`、`scheduler`、`policy` 或 `agent`。实际运行时也可由 payload 覆盖。 |
| `description` | 建议 | 事件语义说明，给 Agent 校验、人工审阅和前端解释使用。 |
| `payload_schema` | 是 | 事件 payload 的结构契约，用来校验事件携带哪些字段、字段类型和含义。 |
| `retention` | 建议 | 事件保留策略，决定 RuntimeSnapshot 或事件日志如何保存该事件。 |

---

## 3. `kind` 取值

当前 v0.2 基线建议只使用以下四类：

| `kind` | 含义 | 典型例子 |
|---|---|---|
| `global_event` | 场景级事件，不隶属于某个设备信号口，通常表达业务阶段或全局事实。 | `runtime.sim_start`、`global.workpiece_claimed`、`global.sorting_done` |
| `device_signal` | 设备实例发出或接收的信号，必须能被对应 `DeviceSpec.signal_ports` 或运行契约解释。 | `main_conveyor_1.pallet_ready`、`conveyor.blocked`、`conveyor.stop_point_occupied`、`robot.pick_done` |
| `control_event` | Runtime、Scheduler 或策略对设备/规则发出的控制类事件。 | `robot.pause_pick`、`robot.resume_pick` |
| `observation` | Runtime 观测到的异常、风险或诊断事件。 | `observation.deadlock_detected`、`observation.overload_detected` |

不建议在正式模板中继续使用 `global`、`device`、`control` 这类简写，避免和设备类型、业务类型混淆。

---

## 4. `payload_schema` 的作用

`payload_schema` 定义事件携带数据的结构。它的核心作用有四个：

- **事件校验**：`SignalBusRuntime` 投递事件前校验 payload 字段是否完整、类型是否正确。
- **规则引用**：`behavior_rules.trigger / guard / policy / action` 可以安全引用 `trigger.payload.xxx`。
- **目标解析**：`routes.target_resolver` 可以从 payload 中解析具体设备、规则或资源目标。
- **前端解释**：前端可根据 schema 展示事件含义、关键字段和当前值。

简单写法：

```json
{
  "event_id": "conveyor.blocked",
  "kind": "device_signal",
  "source": "conveyor",
  "payload_schema": {
    "conveyor_id": "string",
    "current_load": "integer",
    "max_capacity": "integer",
    "reason": "no_stop_point_available | capacity_full | downstream_unavailable"
  },
  "retention": "latest_value"
}
```

更严格写法：

```json
{
  "event_id": "conveyor.blocked",
  "kind": "device_signal",
  "source": "conveyor",
  "payload_schema": {
    "type": "object",
    "required": ["conveyor_id", "current_load", "max_capacity", "reason"],
    "properties": {
      "conveyor_id": {
        "type": "string",
        "description": "发出 blocked 的传送带实例 ID。"
      },
      "current_load": {
        "type": "integer",
        "description": "当前承载数量。"
      },
      "max_capacity": {
        "type": "integer",
        "description": "最大承载数量。"
      },
      "reason": {
        "type": "string",
        "enum": ["no_stop_point_available", "capacity_full", "downstream_unavailable"],
        "description": "阻塞原因：无可用停留点、容量满或下游不可接收。"
      }
    }
  },
  "retention": "latest_value"
}
```

传送带停留点相关事件建议统一使用通用事件 ID，具体是哪条传送带由 payload 指定：

```json
{
  "event_id": "conveyor.stop_point_occupied",
  "kind": "device_signal",
  "source": "conveyor",
  "payload_schema": {
    "conveyor_id": "string",
    "point_id": "string",
    "material_id": "string"
  },
  "retention": "event_log"
}
```

```json
{
  "event_id": "conveyor.stop_point_released",
  "kind": "device_signal",
  "source": "conveyor",
  "payload_schema": {
    "conveyor_id": "string",
    "point_id": "string",
    "material_id": "string"
  },
  "retention": "event_log"
}
```

v0.2 文档示例可以使用简单写法；Runtime 实现时建议转换成严格 JSON Schema 或等价的类型校验结构。

---

## 5. `retention` 取值

| `retention` | 含义 | 适用场景 |
|---|---|---|
| `latest_value` | 只保留最新值，覆盖旧值。 | 设备 blocked 状态、容量状态、当前信号值。 |
| `event_log` | 追加到事件日志，保留历史。 | `sim_start`、`pick_done`、`sorting_done`。 |
| `checkpoint_only` | 不记录每次高频事件，只在 checkpoint 或关键摘要中保存。 | 高频 tick、传送带连续移动帧。 |

---

## 6. `topics` 与 `subscriptions` 标准模板

当 `routes[].to.type == "topic"` 时，`to.id` 不是某条规则，也不是某个设备，而是一个**广播主题 ID**。

例如 `robot_pick_request` 的含义是：“机器人取料请求”这个主题。它本身不执行动作，必须通过 `subscriptions.robot_pick_request` 找到真正消费者。

```json
{
  "topics": [
    {
      "topic_id": "robot_pick_request",
      "description": "托盘到位后广播给所有可参与分拣的机械臂候选规则。",
      "delivery": "broadcast"
    }
  ],
  "subscriptions": {
    "robot_pick_request": [
      {
        "subscriber_type": "rule",
        "subscriber_id": "idle_robot_requests_workpiece",
        "message_event_id": "robot.pick_request",
        "filter": "device_states[robot_1] == idle",
        "payload_template": {
          "robot_id": "robot_1"
        }
      },
      {
        "subscriber_type": "rule",
        "subscriber_id": "idle_robot_requests_workpiece",
        "message_event_id": "robot.pick_request",
        "filter": "device_states[robot_2] == idle",
        "payload_template": {
          "robot_id": "robot_2"
        }
      }
    ]
  }
}
```

执行含义：

1. `main_conveyor_1.pallet_ready` 发生。
2. `SignalBusRuntime` 匹配到 `route_pallet_ready_to_robot_pick_topic`。
3. 该 route 投递到 topic `robot_pick_request`。
4. `SignalBusRuntime` 查 `subscriptions.robot_pick_request`。
5. 对每个订阅项生成一次 `robot.pick_request` 消息，并套用 `payload_template`。
6. Scheduler 用 `robot.pick_request` 唤醒 `idle_robot_requests_workpiece` 规则；规则仍要继续检查 `guard` 和 `policy`，不是广播到了就一定执行。

所以 `robot_pick_request` 是 topic/channel 名；`robot.pick_request` 才是规则 trigger 看到的事件 ID。

---

## 7. `routes` 标准模板

```json
{
  "route_id": "route_pallet_ready_to_robot_pick_topic",
  "from": "main_conveyor_1.pallet_ready",
  "to": {
    "type": "topic",
    "id": "robot_pick_request"
  },
  "delivery": "broadcast",
  "target_resolver": {
    "type": "subscription",
    "path": "event_bus.subscriptions.robot_pick_request"
  }
}
```

### 字段含义

| 字段 | 是否必填 | 含义 |
|---|---:|---|
| `route_id` | 是 | 路由唯一 ID。 |
| `from` | 是 | 触发路由的事件 ID，必须存在于 `event_bus.events`。 |
| `to` | 是 | 投递目标，描述事件要交给哪类消费者。 |
| `to.type` | 是 | 目标类型，例如 `rule`、`topic`、`module`、`device`、`runtime`。 |
| `to.id` | 是 | 目标 ID，例如 `rule_id`、`topic_id`、`module_id`、设备实例 ID 或 Runtime 内部模块名。 |
| `delivery` | 是 | 投递方式，决定是一对一、广播还是 Runtime 内部投递。 |
| `target_resolver` | 可选 | 当目标不能写死时，用于从 payload、binding 或订阅表中解析实际投递对象。 |

---

## 8. `delivery` 取值

| `delivery` | 含义 | 常见目标 |
|---|---|---|
| `direct` | 定向投递给一个明确消费者。 | `rule`、`device`、`runtime` |
| `broadcast` | 广播到 topic 或一组订阅者，由 Scheduler 在下一轮唤醒多个候选规则。 | `topic`、`module` |
| `internal` | 投递给 Runtime 内部模块，不作为设备信号直接暴露。 | `runtime` |

`broadcast` 不是让一个事件自动变成多个新事件，而是把同一个事件分发给多个消费者；消费者是否启动行为仍由对应 `behavior_rules` 的 `trigger + guard + policy` 决定。

---

## 9. `to.type` 取值

| `to.type` | 含义 | 使用建议 |
|---|---|---|
| `rule` | 投递给某条 `behavior_rules[].rule_id`，唤醒该规则进行 `guard / policy / action` 判断。 | v0.2 首选，适合明确的一对一规则唤醒。 |
| `topic` | 投递到逻辑主题，再由 `event_bus.subscriptions[topic_id]` 展开到真正消费者。 | 适合并行分拣、backpressure、全局广播。 |
| `module` | 投递给某个业务模块，模块内规则再自行匹配。 | 适合较大流程阶段，v0.2 可作为扩展。 |
| `device` | 投递给某个设备实例，通常表示设备信号输入或控制输入。 | 需要能映射到 `DeviceSpec.signal_ports`。 |
| `runtime` | 投递给 Runtime 内部模块。 | 适合 `CompletionChecker`、`ObservationEmitter`、`SnapshotManager`。 |

第一阶段建议优先落地 `rule`、`topic`、`runtime`；`module` 和 `device` 可等 Runtime 能力稳定后再扩展。

事件 -> rule：最直接的行为触发路径。事件发生后唤醒某条 behavior_rule，再经过 guard + policy 判断，最终执行 action。例如 runtime.sim_start -> start_pallet_transport。
事件 -> topic：广播路径。事件先投递到 topic，再由 subscriptions[topic_id] 展开成多个消费者，常用于并行设备、候选设备、backpressure 这类“一对多”场景。比如 pallet_ready -> robot_pick_request topic -> robot_1/robot_2 pick_request。
事件 -> runtime：Runtime 内部处理路径。一般用于 CompletionChecker、ObservationEmitter、ReportWriter、SnapshotManager 等，不直接触发设备行为。比如 global.sorting_done -> CompletionChecker。
---

## 10. `target_resolver` 取值

`target_resolver` 只有在“路由目标需要动态解析”时才需要写；如果目标已经明确，例如直接投递给 `start_pallet_transport` 规则，就不需要。

| `target_resolver.type` | 含义 | 示例 |
|---|---|---|
| `static` | 目标固定，通常可省略 `target_resolver`。 | 投递给固定 rule。 |
| `payload_field` | 从事件 payload 字段中取目标。 | `payload.target_conveyor` 指向目标传送带。 |
| `binding` | 从 `event_bus` 中的绑定表解析目标。 | `backpressure_bindings` 根据 conveyor 找 affected robots。 |
| `subscription` | 从 topic 订阅关系中解析所有消费者。 | `robot_pick_request` 展开成多个 `robot.pick_request` 消息并唤醒候选规则。 |

示例：

```json
{
  "route_id": "route_pick_done_to_material_arrival_rule",
  "from": "robot.pick_done",
  "to": {
    "type": "rule",
    "id": "output_conveyor_runs_when_material_arrives"
  },
  "delivery": "direct",
  "target_resolver": {
    "type": "payload_field",
    "path": "payload.target_conveyor"
  }
}
```

这里 `to.id` 说明要唤醒哪条规则，`target_resolver` 说明这条规则内部涉及的具体传送带实例来自 `robot.pick_done` 的 payload。

---

## 11. 推荐执行机制

`event_bus` 在 Runtime 中推荐按离散事件仿真方式执行：

1. `ActionExecutor` 完成行为或策略函数产生事件。
2. `SignalBusRuntime` 校验事件是否存在于 `event_bus.events`，并校验 payload。
3. `SignalBusRuntime` 查找所有 `routes[].from == event_id` 的路由。
4. 根据 `delivery` 和 `to.type` 生成待消费事件项，写入事件队列或调度队列。
5. `Scheduler` 读取被唤醒的 `behavior_rules`，检查 `trigger + guard + policy`。
6. `ActionExecutor` 执行通过校验的行为。
7. `SnapshotManager` 按 `state_transition_rules` 更新 `RuntimeSnapshot`。

这更接近“单线程离散事件仿真中的事件队列 + 发布订阅路由”，而不是前端 Vue EventBus 那种仅用于组件通信的简单回调机制。
