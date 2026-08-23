# Agent Runtime 设计

> 版本：v0.1  
> 日期：2026-08-19  
> 目标：定义 Agent 如何根据用户意图执行、何时触发、如何与实时信号运行时解耦。

---

## 1. 定位

Agent 不是实时控制器。Agent 的职责是：

- 理解用户目标。
- 读取场景、设备规范、接口编译结果和拓扑摘要。
- 生成结构化 artifact。
- 校验、修复、提问、等待确认。
- 在异常或用户打断时触发重规划。

Agent 不负责：

- 每帧控制设备动画。
- 普通信号转发。
- 设备 busy/idle 的毫秒级状态切换。
- 物料等待队列的实时推进。

这些由 Simulation Runtime 的 `SignalBus + Device FSM + Resource Manager` 管理。

---

## 2. 触发时机

| 触发源                    | 示例                           | 进入 Agent 的原因                   |
| ------------------------- | ------------------------------ | ----------------------------------- |
| 用户聊天输入              | “跑一下仿真”“把目标改成 B1”    | 需要理解自然语言和生成 artifact。   |
| 场景结构变化后请求分析    | 用户添加机器人后点击“分析拓扑” | 需要重新编译接口和更新拓扑摘要。    |
| 仿真 observation 失败     | 死锁、超时、目标未达成         | 需要修复计划或询问用户。            |
| 运行中 interrupt / revise | “停一下，换 robot_2”           | 需要暂停 runtime 并重规划剩余动作。 |

普通 `signal_event` 不触发 Agent。只有当 runtime 把信号事件升级为 `simulation_observation`，例如 deadlock 或 timeout，才进入 Agent。

---

## 3. 用户意图分类

`classify_intent` 必须输出结构化 intent：

| intent               | 示例                                 | 输出 artifact                        |
| -------------------- | ------------------------------------ | ------------------------------------ |
| `scene_query`        | “现在场景里有哪些设备？”             | `diagnostic_report`                  |
| `device_edit`        | “把传送带速度改成 0.5m/s”            | `scene_patch`                        |
| `process_connect`    | “让 conveyor_1 接到 robot_1”         | `process_patch`                      |
| `topology_diagnosis` | “为什么跑不起来？”                   | `diagnostic_report`                  |
| `process_config`     | “机器人从传送带抓取并放到右侧传送带” | `process_patch` / `signal_plan`      |
| `simulation_plan`    | “运行 30 分钟仿真”                   | `sim_plan`                           |
| `runtime_revision`   | “停一下，改用 robot_2”               | `question_set` 或 revised `sim_plan` |
| `control`            | “暂停”“取消”“确认执行”               | run control event                    |

---

## 4. LangGraph 工作链路

固定链路：

```text
START
  -> load_scene_snapshot
  -> load_device_specs
  -> compile_interfaces
  -> build_or_load_topology
  -> classify_intent
  -> resolve_slots
  -> route_task
  -> generate_artifact
  -> validate
  -> repair_or_interrupt
  -> apply_or_stage
  -> emit_result
  -> END
```

### 4.1 节点职责

| 节点                     | 类型            |  LLM | 职责                                           |
| ------------------------ | --------------- | ---: | ---------------------------------------------- |
| `load_scene_snapshot`    | 工具            |   否 | 读取 scene、revision、active artifacts。       |
| `load_device_specs`      | 工具            |   否 | 加载实例对应的 DeviceSpec。                    |
| `compile_interfaces`     | 工具            |   否 | 编译流程口到真实接口和信号绑定。               |
| `build_or_load_topology` | 工具            |   否 | 根据 revision 读取或重建拓扑摘要。             |
| `classify_intent`        | LLM 结构化输出  |   是 | 判断用户意图类别。                             |
| `resolve_slots`          | LLM + 工具      |   是 | 将“传送带出口”“A2”“左边机器人”解析为 ID。      |
| `route_task`             | 条件路由        |   否 | 进入查询、编辑、仿真、诊断等分支。             |
| `generate_artifact`      | LLM + 模板      |   是 | 生成结构化 artifact，不写库。                  |
| `validate`               | 工具            |   否 | Schema、revision、拓扑、接口、参数、资源校验。 |
| `repair_or_interrupt`    | 工具 + 可选 LLM | 受限 | 最多修复 2 次，否则提问或失败。                |
| `apply_or_stage`         | 工具            |   否 | 根据 approval policy 暂存或应用。              |
| `emit_result`            | 工具            |   否 | 输出 SSE 事件和最终摘要。                      |

---

## 5. AgentState

```python
class AgentState(TypedDict):
    run_id: str
    thread_id: str
    project_id: str
    scene_id: str
    base_scene_revision: int
    user_message: str

    scene_document: dict | None
    device_specs: dict[str, dict]
    compiled_interfaces: dict | None
    topology_graph: dict | None
    topology_summary: str | None

    intent: dict | None
    slot_resolutions: dict
    active_constraints: dict

    candidate_artifacts: list[dict]
    selected_artifact_id: str | None
    validation_errors: list[dict]
    repair_attempts: int

    pending_interrupt: dict | None
    user_answers: dict
    simulation_snapshot: dict | None

    final_response: str | None
```

---

## 6. Artifact 类型

LLM 只能生成以下结构化 artifact：

| Artifact            | 用途                               |
| ------------------- | ---------------------------------- |
| `scene_patch`       | 修改设备实例、参数、transform。    |
| `process_patch`     | 创建/修改流程连接和工艺配置。      |
| `signal_plan`       | 定义信号依赖、等待条件、超时策略。 |
| `sim_plan`          | 提交给仿真 worker 的执行计划。     |
| `question_set`      | 等待用户澄清或确认。               |
| `diagnostic_report` | 查询、诊断、解释。                 |

禁止直接输出“最终数据库状态”。所有 artifact 都要经过 validator 和 revision check。

---

## 7. Harness 与受控循环

结论：需要 harness，不需要无界 looping agent。

| Harness            | 约束                                            |
| ------------------ | ----------------------------------------------- |
| Schema harness     | 所有 LLM 输出必须符合 Pydantic schema。         |
| Tool harness       | 工具声明输入/输出、超时、幂等性、副作用类型。   |
| Validation harness | 写库或提交仿真前必须确定性校验。                |
| Revision harness   | 所有 scene patch 都绑定 `base_scene_revision`。 |
| Interrupt harness  | 长节点检查 run status 和 cancellation token。   |
| Replay harness     | 保存 node event、artifact、validator result。   |
| Test harness       | 用固定场景 fixture 验证拓扑、slot、SimPlan。    |

允许的循环：

1. `generate -> validate -> repair`，最多 2 次。
2. `proposal -> user revise/approve -> revalidate`，由用户驱动。
3. `runtime observation -> replan remaining`，只在异常或打断时触发。

不允许：

- 无界 self-reflection。
- 每帧调用 LLM。
- 让 LLM 自由推断拓扑或轨迹。

---

## 8. Interrupt / Resume

### 8.1 用户打断

```json
{
  "kind": "revise",
  "message": "停一下，不要用 robot_1，用 robot_2",
  "strategy": "pause_at_safe_point"
}
```

处理流程：

```text
write agent_event:user_interrupt
mark run.pending_interrupt
if simulation running -> request runtime pause
capture RuntimeSnapshot
classify interrupt
merge active_constraints
invalidate affected artifacts
resume graph from checkpoint
validate new artifact
stage or ask user
```

### 8.2 用户确认

```json
{
  "resume_type": "approval",
  "artifact_id": "art_01"
}
```

后端只允许 apply 当前有效 artifact；如果 scene revision 已变化，必须重新 validate。

---

## 9. 何时进入仿真

Agent 只有在以下条件全部满足时才能提交 simulation run：

- `compile_interfaces` 无 blocking error。
- `topology_graph` 无阻塞级错误。
- `sim_plan` schema 校验通过。
- 所有 `signal_plan` 中的 signal ports 存在且方向兼容。
- 所有资源锁和等待条件能被 runtime 表达。
- 如果 approval policy 要求确认，用户已经 approve。

提交后，普通实时信号由 runtime 接管。Agent 只监听 observation：

- deadlock
- timeout
- target_not_reached
- resource_conflict
- user_interrupt
- simulation_failed

---

## 10. 业务示例

用户：“机械臂正在工作时，传送带出口的物料等一下，机械臂完成后再抓取。”

Agent 输出 `signal_plan + sim_plan`：

```json
{
  "signal_plan": {
    "bindings": [
      {
        "when": "robot_1.busy",
        "effect": "conveyor_1.exit.waiting_downstream"
      },
      {
        "when": "robot_1.done",
        "effect": "conveyor_1.release_waiting_material"
      }
    ],
    "timeouts": [
      {
        "signal": "robot_1.done",
        "after_s": 30,
        "on_timeout": "emit_observation"
      }
    ]
  }
}
```

Runtime 执行：

- robot FSM 进入 `busy`。
- conveyor FSM 检测下游 busy，物料进入 waiting queue。
- robot 发送 `done`。
- SignalBus 唤醒 conveyor waiting queue。
- WebSocket 推送 `material_waiting` 和 `signal_event`。
- 无异常时不调用 Agent。
