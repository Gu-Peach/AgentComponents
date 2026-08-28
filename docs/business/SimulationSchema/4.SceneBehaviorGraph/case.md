# SceneBehaviorGraph Policy Cases

> 本文补充 `template.json` 中 `policies` 的完整案例。  
> 范围：当前基线支持的 policy 类型为 `deterministic_priority`、`shared_pool_claim`、`load_balancing`、`capacity_threshold`、`resource_lock`、`queue_wait`、`deadlock_detection`、`timeout_retry`。

---

## 0. Policy 的位置和执行边界

`policy` 分成三层：

| 层级 | 字段 / 模块 | 作用 |
|---|---|---|
| 规则引用 | `behavior_rules[].policy` | 某条规则要调用哪个策略、传入什么参数、把输出绑定到哪里。 |
| 策略定义 | `SceneBehaviorGraph.policies` | 定义策略类型、候选集合、阈值、fallback、超时等参数。 |
| 策略实现 | Runtime `PolicyLibrary` | 可信代码实现策略计算，不把任意函数代码存进 JSON。 |

通用执行流程：

```text
1. Scheduler 根据 trigger 找到候选 behavior_rule。
2. Scheduler 检查 guard。
3. guard 通过后读取 behavior_rule.policy.policy_id。
4. 从 SceneBehaviorGraph.policies 找到策略定义。
5. PolicyLibrary 根据 policies[policy_id].type 执行可信策略实现。
6. 解析 behavior_rule.policy.inputs，得到策略输入。
7. 策略返回 outputs。
8. 按 bind_outputs_to 把 outputs 绑定到 action.payload、action.target 或状态路径。
9. Scheduler 继续申请 resource_locks 并执行 action。
10. SnapshotManager 根据 state_transition_rules 写回 RuntimeSnapshot。
```

注意：

- `policy` 不直接等于 action；它只负责“怎么选、怎么排、是否等待、是否异常”。
- `policy` 不应直接修改业务状态；状态更新应由 `state_transition_rules + SnapshotManager` 统一执行。
- 单线程离散事件仿真中也需要 policy，因为并发语义由 `eventQueue + active_actions + resource_locks` 表达。

---

## 1. 确定性优先级 `deterministic_priority`

### 适用场景

同一个仿真时刻内，多条规则同时满足，需要稳定、可复现的执行顺序。

例如：

```text
runtime.sim_start 同时唤醒多个模块；
两个 robot 同时 idle；
多个 conveyor 同时可继续运输。
```

### `behavior_rules[].policy` 示例

```json
{
  "rule_id": "start_pallet_transport",
  "module_id": "pallet_transport",
  "trigger": {
    "type": "event",
    "event_id": "runtime.sim_start"
  },
  "guard": {
    "all": [
      "device_states.main_conveyor_1 == idle",
      "material_at(pallet_1, main_conveyor_1.entry)"
    ],
    "any": [],
    "none": []
  },
  "policy": {
    "policy_id": "deterministic_priority",
    "inputs": {
      "priority": 1
    }
  },
  "action": {
    "type": "start_behavior",
    "instance_id": "main_conveyor_1",
    "behavior_id": "transport_to_exit",
    "payload": {
      "carrier_id": "pallet_1"
    }
  }
}
```

### `policies` 定义示例

```json
{
  "deterministic_priority": {
    "type": "deterministic_priority",
    "order": [
      "start_pallet_transport",
      "idle_robot_requests_workpiece",
      "claimed_workpiece_starts_pick",
      "output_conveyor_runs_when_material_arrives"
    ],
    "tie_breaker": "rule_id_lexicographic"
  }
}
```

### 流程解释

```text
多条 behavior_rules 在同一 simulation_time 被 trigger 唤醒
  -> Scheduler 分别计算 guard
  -> guard 通过的规则进入 enabled set
  -> PolicyLibrary.deterministic_priority 读取 inputs.priority
  -> 先按 priority 排序
  -> priority 相同时按 policies.deteministic_priority.tie_breaker 排序
  -> Scheduler 按顺序尝试申请资源锁并执行 action
```

输出结果：

```text
enabled_rules_ordered: [rule_id...]
```

---

## 2. 共享工件池 Claim `shared_pool_claim`

### 适用场景

多个 worker 从同一个任务池 / 物料池中领取任务，必须避免重复领取。

例如托盘分拣线：

```text
robot_1 和 robot_2 谁空闲谁从 pallet_1.remaining_parts claim 一个物料。
```

### `behavior_rules[].policy` 示例

```json
{
  "rule_id": "idle_robot_requests_workpiece",
  "module_id": "parallel_robot_sorting",
  "trigger": {
    "type": "event",
    "event_id": "robot.pick_request"
  },
  "guard": {
    "all": [
      "workpiece_pool.pallet_1.remaining_parts.empty == false",
      "device_states[trigger.payload.robot_id] == idle",
      "target_conveyors.blocked_for_robot(trigger.payload.robot_id) == false"
    ],
    "any": [],
    "none": []
  },
  "policy": {
    "policy_id": "claim_workpiece",
    "inputs": {
      "robot_id": "trigger.payload.robot_id",
      "source_pool": "workpiece_pool.pallet_1.remaining_parts"
    },
    "bind_outputs_to": {
      "material_id": "action.payload.material_id"
    }
  },
  "action": {
    "type": "emit_event",
    "event_id": "global.workpiece_claimed",
    "payload": {
      "robot_id": "trigger.payload.robot_id",
      "material_id": "policy.material_id"
    }
  }
}
```

### `policies` 定义示例

```json
{
  "claim_workpiece": {
    "type": "shared_pool_claim",
    "source_pool": "workpiece_pool.pallet_1.remaining_parts",
    "workers": ["robot_1", "robot_2"],
    "selection": "next_available_material",
    "mutual_exclusion": true,
    "on_empty": "emit global.workpiece_pool_empty",
    "on_conflict": "emit observation.claim_conflict_detected"
  }
}
```

### 流程解释

```text
robot.pick_request 到达
  -> Scheduler 找到 idle_robot_requests_workpiece
  -> guard 确认 robot idle、工件池非空、目标传送带未 blocked
  -> PolicyLibrary.shared_pool_claim 读取 source_pool
  -> 选择一个未 claimed 的 material_id
  -> 标记 material_claims[material_id].claimed_by = robot_id
  -> 从 remaining_parts 移入 claimed_parts 或 claims
  -> bind_outputs_to 将 material_id 绑定到 action.payload
  -> action emit global.workpiece_claimed
```

输出结果：

```json
{
  "robot_id": "robot_1",
  "material_id": "part_003",
  "claim_status": "success"
}
```

异常分支：

```text
source_pool 为空
  -> emit global.workpiece_pool_empty

同一 material_id 被重复 claim
  -> emit observation.claim_conflict_detected
```

---

## 3. 目标选择 / 负载均衡 `load_balancing`

### 适用场景

多个目标设备都可能接收物料，需要选择最合适的目标。

例如：

```text
机器人抓到物料后，在 upper_out_conveyor_1 和 lower_out_conveyor_1 中选择一个未 blocked 且负载更低的传送带。
```

### `behavior_rules[].policy` 示例

```json
{
  "rule_id": "claimed_workpiece_starts_pick",
  "module_id": "parallel_robot_sorting",
  "trigger": {
    "type": "event",
    "event_id": "global.workpiece_claimed"
  },
  "guard": {
    "all": [
      "device_states[trigger.payload.robot_id] == idle",
      "material_claims[trigger.payload.material_id].claimed_by == trigger.payload.robot_id"
    ],
    "any": [],
    "none": [
      "target_conveyors.blocked_for_robot(trigger.payload.robot_id) == true"
    ]
  },
  "policy": {
    "policy_id": "target_conveyor_selection",
    "inputs": {
      "robot_id": "trigger.payload.robot_id",
      "material_id": "trigger.payload.material_id"
    },
    "bind_outputs_to": {
      "target_conveyor_id": "action.payload.target_conveyor_id"
    }
  },
  "action": {
    "type": "start_behavior",
    "instance_id": "trigger.payload.robot_id",
    "behavior_id": "pick_and_place",
    "payload": {
      "material_id": "trigger.payload.material_id",
      "target_conveyor_id": "policy.target_conveyor_id"
    }
  }
}
```

### `policies` 定义示例

```json
{
  "target_conveyor_selection": {
    "type": "load_balancing",
    "candidates": ["upper_out_conveyor_1", "lower_out_conveyor_1"],
    "strategy": "choose_non_blocked_lower_load",
    "load_state_path": "conveyor_loads",
    "fallback": "wait_until_capacity_available"
  }
}
```

### 流程解释

```text
global.workpiece_claimed 到达
  -> guard 确认 robot idle 且物料 claim 属于该 robot
  -> PolicyLibrary.load_balancing 读取 candidates
  -> 过滤 blocked == true 的 conveyor
  -> 读取 conveyor_loads.current_load
  -> 选择 current_load 更低的 conveyor
  -> bind_outputs_to 写入 action.payload.target_conveyor_id
  -> ActionExecutor 启动 pick_and_place
```

输出结果：

```json
{
  "target_conveyor_id": "upper_out_conveyor_1",
  "reason": "non_blocked_lower_load"
}
```

异常分支：

```text
所有 candidates 都 blocked
  -> fallback = wait_until_capacity_available
  -> 转入 queue_wait 或等待 capacity_available 事件
```

---

## 4. 容量阈值 / Backpressure `capacity_threshold`

### 适用场景

下游设备容量有限，需要通过 blocked / capacity_available 反馈控制上游设备。

例如：

```text
出料传送带 current_load >= max_capacity 时暂停绑定机械臂；
current_load <= resume_threshold 时恢复机械臂抓取。
```

### `behavior_rules[].policy` 示例

```json
{
  "rule_id": "blocked_conveyor_pauses_robot",
  "module_id": "parallel_robot_sorting",
  "trigger": {
    "type": "event",
    "event_id": "output_conveyor.blocked"
  },
  "guard": {
    "all": [
      "conveyor_loads[trigger.payload.conveyor_id].blocked == true"
    ],
    "any": [],
    "none": []
  },
  "policy": {
    "policy_id": "backpressure",
    "inputs": {
      "conveyor_id": "trigger.payload.conveyor_id"
    },
    "bind_outputs_to": {
      "target_robots": "action.target"
    }
  },
  "action": {
    "type": "emit_event",
    "event_id": "robot.pause_pick",
    "target": "policy.target_robots",
    "payload": {
      "reason": "target_conveyor_blocked",
      "conveyor_id": "trigger.payload.conveyor_id"
    }
  }
}
```

### `policies` 定义示例

```json
{
  "backpressure": {
    "type": "capacity_threshold",
    "state_path": "conveyor_loads",
    "blocked_when": "current_load >= max_capacity",
    "resume_when": "current_load <= resume_threshold",
    "blocked_event": "output_conveyor.blocked",
    "available_event": "output_conveyor.capacity_available",
    "target_resolver": "robots_bound_to_conveyor"
  }
}
```

### 流程解释

```text
output_conveyor.material_arrived 到达
  -> state_transition_rules 增加 conveyor_loads[conveyor_id].current_load
  -> PolicyLibrary.capacity_threshold 读取 current_load / max_capacity / resume_threshold
  -> 如果 current_load >= max_capacity
       set conveyor_loads[conveyor_id].blocked = true
       emit output_conveyor.blocked
  -> blocked_conveyor_pauses_robot 被 trigger 唤醒
  -> policy.target_resolver 找到绑定 robot
  -> action emit robot.pause_pick
```

恢复流程：

```text
物料离开出料传送带
  -> current_load 下降
  -> 如果 current_load <= resume_threshold
       set blocked = false
       emit output_conveyor.capacity_available
  -> capacity_available_resumes_robot 被 trigger 唤醒
  -> emit robot.resume_pick
```

输出结果：

```json
{
  "blocked": true,
  "target_robots": ["robot_1"],
  "event_id": "output_conveyor.blocked"
}
```

---

## 5. 资源锁 `resource_lock`

### 适用场景

行为启动前，需要保证设备资源或物料资源没有被其他 action 占用。

例如：

```text
robot_1.gripper 同一时刻只能被一个 pick_and_place action 占用。
main_conveyor_1.belt_surface 同一时刻只能执行一个主要 transport action。
```

### `behavior_rules[].policy` 示例

```json
{
  "rule_id": "robot_pick_resource_check",
  "module_id": "parallel_robot_sorting",
  "trigger": {
    "type": "event",
    "event_id": "global.workpiece_claimed"
  },
  "guard": {
    "all": [
      "device_states[trigger.payload.robot_id] == idle"
    ],
    "any": [],
    "none": []
  },
  "policy": {
    "policy_id": "resource_lock",
    "inputs": {
      "resources": [
        "${trigger.payload.robot_id}.gripper",
        "${trigger.payload.robot_id}.robot_arm"
      ],
      "mode": "exclusive"
    },
    "bind_outputs_to": {
      "lock_owner": "runtime.resource_locks.owner_action_id"
    }
  },
  "action": {
    "type": "start_behavior",
    "instance_id": "trigger.payload.robot_id",
    "behavior_id": "pick_and_place",
    "payload": {
      "material_id": "trigger.payload.material_id"
    }
  }
}
```

### `policies` 定义示例

```json
{
  "resource_lock": {
    "type": "resource_lock",
    "lock_mode": "exclusive",
    "on_lock_failed": "queue_or_skip",
    "release_on": ["behavior_completed", "behavior_failed", "behavior_cancelled"]
  }
}
```

### 流程解释

```text
guard 通过
  -> PolicyLibrary.resource_lock 解析 resources
  -> 检查 RuntimeSnapshot.resource_locks
  -> 全部为空则 acquire
  -> 写入 owner_action_id
  -> Scheduler 启动 action
  -> action 完成 / 失败 / 取消后 release
```

输出结果：

```json
{
  "lock_status": "acquired",
  "resources": ["robot_1.gripper", "robot_1.robot_arm"],
  "owner_action_id": "action_robot_1_pick_part_003"
}
```

异常分支：

```text
任一资源已被占用
  -> on_lock_failed = queue_or_skip
  -> action 不启动
  -> 可进入 queue_wait 或等待下一轮 scheduler_tick
```

---

## 6. 等待队列 `queue_wait`

### 适用场景

当前不能执行，但不是异常，而是需要等待某个释放事件。

例如：

```text
目标传送带 blocked，robot 暂不 claim 新物料；
等待 output_conveyor.capacity_available 后恢复。
```

### `behavior_rules[].policy` 示例

```json
{
  "rule_id": "wait_for_output_capacity",
  "module_id": "parallel_robot_sorting",
  "trigger": {
    "type": "event",
    "event_id": "output_conveyor.blocked"
  },
  "guard": {
    "all": [
      "conveyor_loads[trigger.payload.conveyor_id].blocked == true"
    ],
    "any": [],
    "none": []
  },
  "policy": {
    "policy_id": "queue_wait",
    "inputs": {
      "queue_id": "wait_queues.output_capacity",
      "item": "robots_bound_to_conveyor(trigger.payload.conveyor_id)",
      "release_event": "output_conveyor.capacity_available"
    }
  },
  "action": {
    "type": "update_state",
    "payload": {
      "state_path": "wait_queues.output_capacity",
      "operation": "append_unique"
    }
  }
}
```

### `policies` 定义示例

```json
{
  "queue_wait": {
    "type": "queue_wait",
    "queue_state_path": "wait_queues",
    "release_event": "output_conveyor.capacity_available",
    "ordering": "fifo",
    "timeout_ms": 30000,
    "on_timeout": "emit observation.queue_timeout"
  }
}
```

### 流程解释

```text
blocked 事件到达
  -> guard 确认 conveyor blocked
  -> PolicyLibrary.queue_wait 构造等待项
  -> action update_state 将 robot/action 放入 wait_queues.output_capacity
  -> release_event 到达
  -> SignalBusRuntime 投递 capacity_available
  -> Scheduler 重新唤醒相关 rule
  -> 从 wait_queues 中释放等待项
```

输出结果：

```json
{
  "queue_id": "wait_queues.output_capacity",
  "queued_items": ["robot_1"],
  "release_event": "output_conveyor.capacity_available"
}
```

---

## 7. 死锁检测 `deadlock_detection`

### 适用场景

Runtime 发现没有可执行行为，但任务尚未完成。

例如：

```text
工件池未空；
robot 都在等待 output capacity；
conveyor 又没有 active action 可以降低负载；
completion_conditions 未满足。
```

### `behavior_rules[].policy` 示例

```json
{
  "rule_id": "detect_deadlock_on_scheduler_tick",
  "module_id": "runtime_observation",
  "trigger": {
    "type": "scheduler_tick"
  },
  "guard": {
    "all": [
      "completion_conditions.unsatisfied == true"
    ],
    "any": [],
    "none": [
      "enabled_rules.exists == true",
      "active_actions.progressing == true"
    ]
  },
  "policy": {
    "policy_id": "deadlock_detection",
    "inputs": {
      "active_actions": "active_actions",
      "pending_events": "eventQueue.pending",
      "wait_queues": "wait_queues",
      "resource_locks": "resource_locks",
      "completion_conditions": "completion_conditions"
    }
  },
  "action": {
    "type": "emit_event",
    "event_id": "observation.deadlock_detected",
    "payload": {
      "wait_chain": "policy.wait_chain",
      "blocked_resources": "policy.blocked_resources"
    }
  }
}
```

### `policies` 定义示例

```json
{
  "deadlock_detection": {
    "type": "deadlock_detection",
    "condition": "no_enabled_rules and no_progress and completion_conditions.unsatisfied",
    "emit": "observation.deadlock_detected",
    "include_wait_chain": true,
    "include_resource_locks": true
  }
}
```

### 流程解释

```text
Scheduler 一轮调度结束
  -> 没有 enabled rules
  -> active_actions 为空或长期无进展
  -> eventQueue 没有可推进事件
  -> completion_conditions 仍未满足
  -> PolicyLibrary.deadlock_detection 构造 wait_chain
  -> action emit observation.deadlock_detected
```

输出结果：

```json
{
  "deadlock": true,
  "wait_chain": [
    "robot_1 waits output_conveyor.capacity_available",
    "upper_out_conveyor_1 blocked and no active transport action"
  ],
  "blocked_resources": ["upper_out_conveyor_1.belt_surface"]
}
```

---

## 8. 超时 / 重试 `timeout_retry`

### 适用场景

动作、队列等待或信号等待超过阈值，需要重试或发出异常观测。

例如：

```text
robot_1.pick_and_place 超过 30 秒未完成；
等待 output_conveyor.capacity_available 超时；
设备 done 信号迟迟未返回。
```

### `behavior_rules[].policy` 示例

```json
{
  "rule_id": "retry_or_fail_timeout_action",
  "module_id": "runtime_observation",
  "trigger": {
    "type": "scheduler_tick"
  },
  "guard": {
    "all": [
      "active_actions.exists_timeout == true"
    ],
    "any": [],
    "none": []
  },
  "policy": {
    "policy_id": "timeout_retry",
    "inputs": {
      "action_id": "runtime.timeout_action_id",
      "timeout_ms": 30000,
      "retry_limit": 2
    },
    "bind_outputs_to": {
      "next_event": "action.event_id",
      "retry_count": "action.payload.retry_count"
    }
  },
  "action": {
    "type": "emit_event",
    "event_id": "policy.next_event",
    "payload": {
      "action_id": "runtime.timeout_action_id",
      "retry_count": "policy.retry_count"
    }
  }
}
```

### `policies` 定义示例

```json
{
  "timeout_retry": {
    "type": "timeout_retry",
    "timeout_ms": 30000,
    "retry_limit": 2,
    "retry_event": "runtime.retry_action",
    "on_retry_exhausted": "observation.action_timeout"
  }
}
```

### 流程解释

```text
ActionExecutor 启动 action
  -> RuntimeSnapshot.active_actions 记录 started_at 和 retry_count
  -> Scheduler / ObservationEmitter 在 scheduler_tick 检查运行时长
  -> 如果 now - started_at > timeout_ms 且 retry_count < retry_limit
       emit runtime.retry_action
  -> 如果 retry_count >= retry_limit
       emit observation.action_timeout
```

输出结果：

```json
{
  "timeout": true,
  "next_event": "runtime.retry_action",
  "retry_count": 1
}
```

---

## 9. 托盘分拣线综合流程

以下流程展示多个 policy 如何在单线程离散事件仿真中协同：

```text
runtime.sim_start
  -> deterministic_priority 选择 start_pallet_transport 优先执行
  -> resource_lock 占用 main_conveyor_1.belt_surface
  -> action start main_conveyor_1.transport_to_exit

main_conveyor_1.pallet_ready
  -> deterministic_priority 排序 robot pick_request
  -> shared_pool_claim 为 robot_1 / robot_2 分别 claim 不同物料
  -> load_balancing 为每个物料选择未 blocked 且低负载的出料传送带
  -> resource_lock 占用 robot.gripper / robot_arm
  -> action start robot.pick_and_place

output_conveyor.material_arrived
  -> capacity_threshold 检查 current_load
  -> 若超阈值，emit output_conveyor.blocked
  -> queue_wait 暂存受影响 robot 的后续抓取请求

output_conveyor.capacity_available
  -> queue_wait 释放等待项
  -> deterministic_priority 重新排序可执行规则
  -> robot 恢复 claim / pick

scheduler_tick
  -> timeout_retry 检查超时 action
  -> deadlock_detection 检查是否无可执行规则且未完成
```

总结：

```text
deterministic_priority 保证顺序可复现；
shared_pool_claim 解决多机械臂抢料；
load_balancing 选择目标传送带；
capacity_threshold 实现 backpressure；
resource_lock 保证资源互斥；
queue_wait 处理临时不可执行；
deadlock_detection 发现无进展异常；
timeout_retry 处理动作或等待超时。
```

---

## 10. 当前优先级

| 优先级 | policy type | 原因 |
|---|---|---|
| P0 | `deterministic_priority` | 保证单线程 DES 可复现。 |
| P0 | `shared_pool_claim` | 支撑双机械臂共享工件池。 |
| P0 | `load_balancing` | 支撑目标传送带动态选择。 |
| P0 | `capacity_threshold` | 支撑 backpressure。 |
| P0 | `resource_lock` | 保证设备资源互斥。 |
| P1 | `queue_wait` | 支撑下游等待和排队。 |
| P1 | `deadlock_detection` | 支撑异常观测。 |
| P2 | `timeout_retry` | 支撑动作超时和恢复。 |
