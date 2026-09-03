# SceneBehaviorGraph Agent 验证方案

> 目标：为后续构造更多测试 case 提供统一评估框架，用于验证 `scene_behavior_agent` 是否能从 `SceneDocument + DeviceSpec + 用户目标` 生成合规、准确、可解释的最终工艺行为图 `SceneBehaviorGraph`。

---

## 1. 验证对象与边界

### 1.1 验证对象

当前验证对象是 **离线工艺建模 Agent 的最终输出**：`SceneBehaviorGraph`。

```text
DeviceSpec + SceneDocument + 用户目标
  -> LangGraph Agent
  -> SceneBehaviorGraph
```

验证不以中间节点结果作为主要判卷对象，而是以最终行为图为核心依据。原因是每个工具节点和模型节点的关键结果最终都会被覆盖到 `SceneBehaviorGraph` 中：

| Agent 阶段 | 最终图中的对应位置 |
|---|---|
| 场景读取与连接理解 | `goal.assumptions`、`modules`、`event_bus.routes`、`state_model` |
| 设备能力读取 | `behavior_rules.action`、`state_transition_rules.effects`、`policies` |
| 用户意图解析 | `goal`、`modules`、`completion_conditions`、`failure_observations` |
| 事件与状态建模 | `event_bus`、`state_model` |
| 行为规则建模 | `behavior_rules`、`state_transition_rules` |
| 策略选择 | `policies`、`failure_observations` |
| 图组装与校验 | `SceneBehaviorGraph` 顶层结构、引用完整性、字段规范 |

因此，Agent 验证可以收敛为：**基于最终图验证结构合规性与语义准确性**。

### 1.2 不在本阶段验证的内容

| 不验证项 | 原因 |
|---|---|
| Runtime 高频执行性能 | 属于 Runtime Scheduler 验证，不属于 Agent 最终图生成准确性。 |
| SimPy / DES 事件队列实现 | 这是 Runtime 执行参考，不是 Agent 的建模输出。 |
| 真实物理运动学精度 | 当前行为图验证的是工艺行为和调度语义，不验证 3D 运动轨迹。 |
| 用户中途改需求重规划 | 当前基线先不处理运行中重规划。 |
| 旧 schema 兼容性 | 当前只验证 `SceneBehaviorGraph`，不验证旧 `SimPlan / SignalBusSchema / SceneTransportSchema`。 |

---

## 2. 总体验证思路

Agent 验证从两个维度展开，但两个维度都以最终 `SceneBehaviorGraph` 为判卷对象。

```text
SceneBehaviorGraph
  -> 结构合规性验证
  -> LLM 调度结果准确性验证
```

### 2.1 维度一：最终行为图是否合规

验证最终图是否符合 schema 规范，包括：

- 必填 section 是否存在。
- 字段结构是否符合模板定义。
- 引用关系是否完整。
- 旧 schema 字段是否被排除。
- `event_bus / state_model / behavior_rules / state_transition_rules / policies` 是否具备可校验结构。

这一维度主要回答：

```text
Agent 是否生成了一个结构正确、字段完整、引用合法的 SceneBehaviorGraph？
```

### 2.2 维度二：LLM 调度结果是否准确

验证 LLM 是否正确理解用户意图，并把意图映射为合理的场景行为图。

这一维度的验证入口仍然是最终图，但关注语义层面：

- 用户目标是否被覆盖。
- 场景模块是否符合业务流程。
- 事件是否覆盖该场景会发生的关键离散事件。
- 事件路由是否表达正确协作关系。
- 状态模型是否包含 Runtime 需要维护的关键状态。
- 行为规则是否能把事件、状态、策略和设备行为连接起来。
- 状态迁移规则是否能推进流程闭环。
- 策略函数是否解决共享资源、容量、阻塞、断点等待、死锁等动态问题。

这一维度主要回答：

```text
Agent 是否把用户目标和场景事实，正确建模成可执行语义的 SceneBehaviorGraph？
```

### 2.3 验证粒度

当前方案不把节点级中间状态作为主要验收标准。

| 粒度 | 当前用途 |
|---|---|
| 最终图验证 | 主要验证方式，用于 case benchmark 和准确性评估。 |
| 节点过程日志 | 辅助 debug，用于定位为什么最终图错误。 |
| 工具单测 | 工程质量保障，用于验证工具本身可用，但不作为 Agent 准确性主指标。 |

---

## 3. 最终行为图合规性验证

### 3.1 JSON 与顶层结构

检查点：

- 输出 JSON 可以被解析。
- 输出对象明确是 `SceneBehaviorGraph`。
- 顶层字段完整。
- 顶层字段类型正确。

必填 section：

| Section | 作用 |
|---|---|
| `goal` | 用户目标、建模边界、场景假设。 |
| `modules` | 场景运行模块。 |
| `event_bus` | 事件注册、topic、路由和投递规则。 |
| `state_model` | Runtime 需要维护的状态变量。 |
| `behavior_rules` | 事件 + guard + policy 到 action 的行为触发规则。 |
| `state_transition_rules` | 行为开始、完成、失败、事件触发后的状态变更。 |
| `policies` | 动态策略函数配置。 |
| `completion_conditions` | 场景完成条件。 |
| `failure_observations` | 异常观测与失败条件。 |

推荐指标：

| 指标 | 含义 |
|---|---|
| `json_parse_success` | 输出是否为合法 JSON。 |
| `schema_type_correct` | 是否为 `SceneBehaviorGraph`。 |
| `required_section_coverage` | 必填 section 覆盖率。 |
| `field_type_validity` | 关键字段类型是否正确。 |

### 3.2 禁止旧 schema 污染

最终图中不应出现旧链路产物或旧字段。

禁止出现：

- `SceneTransportSchema`
- `SignalBusSchema`
- `SimPlan`
- `ExecutableSimGraph`
- `DeviceRuntimeProfile`
- `scene_transport_schema`
- `signal_bus_schema`
- `sim_plan`
- `executable_sim_graph`
- `device_runtime_profile`
- `when_event`
- `when_state`
- `then_start_behavior`
- `then_emit_signal`

推荐指标：

| 指标 | 含义 |
|---|---|
| `legacy_schema_violation_count` | 旧 schema 名称或字段出现次数。 |
| `legacy_schema_violation_rate` | 出现旧 schema 污染的 case 占比。 |

### 3.3 引用完整性

最终图中所有引用必须能追溯到输入或图内声明。

检查点：

- `behavior_rules.action.instance_id` 存在于 `SceneDocument.instances`。
- `behavior_rules.action.behavior_id` 存在于对应 `DeviceSpec.transport_behaviors`。
- `event_bus.routes[].from` 存在于 `event_bus.events`。
- `behavior_rules.trigger.event_id` 存在于 `event_bus.events`，或由 topic subscription 生成。
- `trigger.payload.xxx` 能从对应事件的 `payload_schema` 推导。
- `guard / policy / action / effects` 引用的状态变量存在于 `state_model`。
- `state_transition_rules.effects.emit` 的事件已经在 `event_bus.events` 注册。
- `resource_locks` 引用的资源可被设备能力或行为资源定义解释。

推荐指标：

| 指标 | 含义 |
|---|---|
| `instance_reference_precision` | 设备实例引用正确率。 |
| `behavior_reference_precision` | 行为 ID 引用正确率。 |
| `event_reference_precision` | 事件引用正确率。 |
| `state_reference_precision` | 状态变量引用正确率。 |
| `payload_reference_validity` | payload 字段引用有效率。 |

### 3.4 规则结构合规

检查点：

- `behavior_rules` 每条规则包含 `rule_id / module_id / trigger / guard / policy / action`。
- `trigger` 明确事件来源。
- `guard` 使用 `all / any / none` 表达前置条件。
- `policy` 明确策略 ID 和输入参数。
- `action` 明确行为类型、目标设备和行为 ID。
- `state_transition_rules` 明确 trigger、effects 和适用 action / behavior。

推荐指标：

| 指标 | 含义 |
|---|---|
| `rule_form_compliance` | 行为规则格式合规率。 |
| `transition_form_compliance` | 状态迁移规则格式合规率。 |
| `policy_form_compliance` | 策略配置格式合规率。 |

---

## 4. LLM 调度结果准确性验证

### 4.1 用户目标覆盖度

验证 LLM 是否正确理解用户目标，并把目标落到最终图。

检查点：

- 用户目标中的关键动作是否进入 `modules / behavior_rules`。
- 用户目标中的执行顺序是否进入模块关系、事件链路或 guard。
- 用户目标中的并行、持续运行是否通过模块类型、规则和策略表达。
- 用户目标中的约束是否进入 `guard / policy / completion_conditions / failure_observations`。
- 用户目标中的异常处理要求是否进入策略函数或 observation。
- 用户目标中的完成定义是否进入 `completion_conditions`。

推荐指标：

| 指标 | 含义 |
|---|---|
| `goal_requirement_coverage` | 用户目标关键需求覆盖率。 |
| `module_mapping_accuracy` | 工艺模块拆分是否匹配用户目标。 |
| `constraint_mapping_accuracy` | 约束是否映射到状态、规则、策略或完成条件。 |
| `missing_requirement_count` | 未覆盖的用户需求数量。 |

### 4.2 场景模块准确性

验证 `modules` 是否表达了正确的工艺阶段和运行关系。

检查点：

- 模块划分符合用户描述的业务过程。
- 顺序模块、并行模块、持续运行模块区分正确。
- 模块之间的开始、完成、并行协作关系可以通过事件链路解释。
- 模块没有遗漏关键设备或物料。

推荐指标：

| 指标 | 含义 |
|---|---|
| `module_coverage` | 期望模块覆盖率。 |
| `module_order_accuracy` | 模块顺序关系正确性。 |
| `parallel_module_accuracy` | 并行 / 持续运行模块表达准确性。 |

### 4.3 事件与事件路由准确性

验证 `event_bus` 是否表达该场景下会发生的关键事件和协作关系。

检查点：

- 关键业务事件是否注册在 `event_bus.events`。
- 事件类型是否正确区分设备信号、全局事件、控制事件、observation。
- `payload_schema` 是否包含路由、规则、策略和 action 所需参数。
- 路由是否表达事件投递方向。
- topic 是否被正确用于广播、订阅和一对多派发。
- runtime 内部事件是否用于完成检查、异常检查、报告输出等 Runtime 内部动作。
- 关键业务链路是否能从起点事件 trace 到终点事件。

推荐指标：

| 指标 | 含义 |
|---|---|
| `event_registration_completeness` | 关键事件注册完整度。 |
| `route_semantic_accuracy` | 路由表达的协作关系是否正确。 |
| `topic_subscription_coverage` | topic 是否存在有效订阅者。 |
| `event_chain_completeness` | 关键事件链路是否闭合。 |

### 4.4 状态模型准确性

验证 `state_model` 是否包含 Runtime 执行该行为图所需的状态事实。

检查点：

- 设备状态：`device_states`。
- 信号值：`signal_values`。
- active action：`active_actions`。
- 资源锁：`resource_locks`。
- 物料位置、物料池、claim 状态。
- 传送带负载、队列、断点、占用情况。
- 特定场景状态，例如旋转台工位占用、工作台占用、缓存区容量等。

推荐指标：

| 指标 | 含义 |
|---|---|
| `state_variable_coverage` | 期望状态变量覆盖率。 |
| `state_rule_consistency` | 规则引用的状态变量是否存在。 |
| `transition_state_consistency` | 状态迁移修改的状态是否已声明。 |
| `runtime_readiness_score` | Runtime 初始化快照所需状态是否完整。 |

### 4.5 行为规则准确性

验证 `behavior_rules` 是否正确描述事件触发、状态前置、策略决策和设备行为之间的关系。

检查点：

- `trigger` 是否对应正确事件。
- `guard` 是否表达行为启动前必须满足的状态条件。
- `policy` 是否解决该行为的动态决策问题。
- `action` 是否调用正确设备的正确行为。
- 多条规则之间是否不会导致明显冲突或重复启动。

推荐指标：

| 指标 | 含义 |
|---|---|
| `trigger_validity` | trigger 事件有效率。 |
| `guard_relevance` | guard 是否覆盖关键前置条件。 |
| `policy_relevance` | policy 是否匹配动态决策需求。 |
| `action_validity` | action 是否引用合法且语义正确。 |

### 4.6 状态迁移准确性

验证 `state_transition_rules` 是否能让行为执行后继续推进场景闭环。

检查点：

- 行为开始时是否更新设备状态和资源锁。
- 行为完成时是否释放资源、移动物料、更新负载、发出后续事件。
- 行为失败时是否更新异常状态并触发 observation。
- 连续状态跨阈值时是否发出离散事件，例如 `blocked / capacity_available`。
- 完成条件所依赖的状态是否会被迁移规则更新。

推荐指标：

| 指标 | 含义 |
|---|---|
| `transition_effect_coverage` | 关键行为是否有状态迁移规则。 |
| `emitted_event_registration_rate` | effects 中 emit 的事件是否已注册。 |
| `resource_release_completeness` | 资源锁是否在完成或失败后释放。 |
| `completion_state_reachability` | 完成条件依赖状态是否可达。 |

### 4.7 策略函数适配度

验证 `policies` 是否覆盖该场景的动态决策问题。

常见策略映射：

| 场景问题 | 期望策略 |
|---|---|
| 多机器人抢同一物料 | `shared_pool_claim` |
| 多出料传送带选择 | `load_balancing` / `least_loaded_target` |
| 传送带容量限制 | `capacity_threshold` / `backpressure` |
| 传送带断点等待 | `queue_wait` / `nearest_available_stop_point` / `downstream_release` |
| 资源互斥 | `resource_lock` |
| 长时间无可执行行为 | `deadlock_detection` |
| 动作超时 | `timeout_retry` |

推荐指标：

| 指标 | 含义 |
|---|---|
| `policy_selection_accuracy` | 是否选择了正确策略类型。 |
| `policy_parameter_correctness` | 策略参数是否绑定正确状态变量和设备。 |
| `dynamic_conflict_coverage` | 是否覆盖资源冲突、容量冲突、抢占冲突。 |

### 4.8 完成条件与异常观测准确性

验证最终图是否能定义清晰的终止条件和异常观测。

检查点：

- `completion_conditions` 是否覆盖用户目标中的完成定义。
- 完成条件是否可由 `state_model` 和 `state_transition_rules` 判定。
- `failure_observations` 是否覆盖场景关键异常。
- 异常观测是否能通过状态变量、事件或策略函数触发。

推荐指标：

| 指标 | 含义 |
|---|---|
| `completion_condition_accuracy` | 完成条件是否准确。 |
| `completion_condition_checkability` | 完成条件是否可由 RuntimeSnapshot 判定。 |
| `failure_observation_coverage` | 关键异常观测覆盖率。 |

---

## 5. Case 类型设计

后续新增 case 应覆盖不同工艺语义、动态策略和失败模式。Case 类型设计保持有效，所有 case 最终都通过 `SceneBehaviorGraph` 做结构和语义验证。

### 5.1 正向基础 case

目标：验证 Agent 能生成完整、合规、语义正确的基础行为图。

例子：

- 单传送带运输。
- 两段传送带交接。
- 单机械臂搬运。
- 托盘到位后机械臂分拣。

重点断言：

- 必填 section 完整。
- 模块和事件链路完整。
- 行为规则引用合法。
- 完成条件可判定。

### 5.2 并行协作 case

目标：验证 Agent 能表达多设备并行、共享资源和动态选择。

例子：

- 双机械臂共享工件池。
- 多出料传送带负载均衡。
- 多工位旋转台 + 机械臂下料。
- 多机器人协同搬运同一批物料。

重点断言：

- `modules` 表达并行或持续运行。
- `state_model` 包含共享池、claim、资源锁或设备状态。
- `policies` 包含共享资源或调度策略。
- `behavior_rules` 不产生重复 claim 或资源冲突。

### 5.3 连续过程与离散事件 case

目标：验证 Agent 能把连续状态变化建模为离散事件触发。

例子：

- 传送带负载达到上限触发 `blocked`。
- 负载降到恢复阈值触发 `capacity_available`。
- 传送带断点被占用 / 释放。
- stop point queue 等待和 downstream release。

重点断言：

- `state_model` 包含连续状态变量，如负载、队列、断点占用。
- `policies` 包含阈值判断或 backpressure。
- `state_transition_rules` 能在阈值跨越时 emit 离散事件。
- `event_bus.routes` 能把离散事件投递到对应规则或 Runtime 内部模块。

### 5.4 异常与负向 case

目标：验证 Agent 能在最终图或验证报告中暴露无法建模的问题，而不是硬编出错误行为图。

例子：

- 用户要求设备执行不存在的行为。
- SceneDocument 缺少必要连接。
- signal edge 引用不存在端口。
- 设备规范缺失。
- 用户目标要求中途重规划，但当前基线不支持。

重点断言：

- 合规 case 不应生成非法引用。
- 不可建模 case 应在 `failure_observations / validation_report / explanation` 中明确说明原因。
- 不应凭空发明设备、行为、信号或状态变量。

### 5.5 语义干扰 case

目标：验证 Agent 不被无关信息、旧 schema 名称或模糊表达污染。

例子：

- 用户描述中混入旧 schema 名称。
- 用户要求生成 `SimPlan`，但当前基线应输出 `SceneBehaviorGraph`。
- 场景描述模糊，需要输出 assumptions / open questions。
- 用户使用口语化表达，例如“别堵住传送带”“谁空谁拿”。

重点断言：

- 最终图仍然是 `SceneBehaviorGraph`。
- 不出现旧 schema 字段。
- 口语化约束能映射为状态、策略或异常观测。
- 模糊条件能进入 `goal.assumptions` 或解释内容。

---

## 6. Case 文件结构

建议沿用当前目录结构，并用机器可读断言描述对最终图的期望。

```text
docs/test/case/scene_XX/
  README.md
  normalized_case.md
  scene_document.input.json
  device_specs.input.json
  scene_behavior_graph.golden.json
  graph_explanation.md
  test_assertions.json
  validation_report.md
```

### 6.1 `normalized_case.md`

用于描述测试输入和评估意图。

建议包含：

- 场景摘要。
- 用户目标。
- 设备列表。
- 物料列表。
- 显式连接。
- 期望工艺行为。
- 关键约束。
- 应触发的策略。
- 完成条件。
- 异常观测要求。

### 6.2 `test_assertions.json`

用于描述最终图断言，不关心中间节点状态。

推荐结构：

```json
{
  "case_id": "scene_XX_example",
  "schema_assertions": {
    "required_sections": [
      "goal",
      "modules",
      "event_bus",
      "state_model",
      "behavior_rules",
      "state_transition_rules",
      "policies",
      "completion_conditions",
      "failure_observations"
    ],
    "forbidden_fields": [
      "sim_plan",
      "signal_bus_schema",
      "scene_transport_schema",
      "executable_sim_graph",
      "device_runtime_profile",
      "when_event",
      "when_state"
    ]
  },
  "semantic_assertions": {
    "must_have_modules": [],
    "must_have_events": [],
    "must_have_routes": [],
    "must_have_state_variables": [],
    "must_have_behavior_rules": [],
    "must_have_transition_effects": [],
    "must_have_policies": [],
    "must_have_completion_conditions": [],
    "must_have_failure_observations": []
  },
  "reference_assertions": {
    "all_action_instances_exist": true,
    "all_action_behaviors_exist_in_device_spec": true,
    "all_trigger_events_registered": true,
    "all_route_sources_registered": true,
    "all_state_references_declared": true
  }
}
```

### 6.3 `scene_behavior_graph.golden.json`

`golden` 不要求和 Agent 输出逐字一致，只作为关键语义参考。

建议比较方式：

- 比较必须存在的模块、事件、状态变量、规则、策略。
- 比较关键事件链路是否闭合。
- 比较核心策略是否存在且参数绑定合理。
- 不比较字段顺序和自然语言描述的逐字内容。

### 6.4 `validation_report.md`

每个 case 的验证报告应围绕最终图输出。

建议结构：

```markdown
# scene_XX Validation Report

## Result
- schema_valid: true | false
- semantic_valid: true | false
- pass: true | false

## Schema Compliance
- required_section_coverage: ...
- legacy_schema_violation_count: ...
- reference_errors: ...

## Semantic Accuracy
- goal_requirement_coverage: ...
- event_chain_completeness: ...
- state_model_coverage: ...
- policy_selection_accuracy: ...

## Failed Assertions
...

## Notes
...
```

---

## 7. 推荐执行流程

### 7.1 单 case 执行

```text
1. 读取 scene_XX/normalized_case.md。
2. 准备 SceneDocument 和 DeviceSpec 输入。
3. 调用 scene_behavior_agent 生成 SceneBehaviorGraph。
4. 对最终 SceneBehaviorGraph 运行 schema 合规性校验。
5. 对最终 SceneBehaviorGraph 运行 semantic assertions。
6. 如存在 golden，进行关键语义对比。
7. 生成 validation_report.md。
```

### 7.2 全量 benchmark 执行

```text
for each case in docs/test/case/scene_*:
  run agent
  validate final SceneBehaviorGraph schema
  run semantic assertions on final SceneBehaviorGraph
  compare semantic golden if present
  write per-case validation_report.md
aggregate reports
write benchmark_summary.md
```

---

## 8. 指标体系

### 8.1 单 case 指标

| 指标 | 含义 | 期望 |
|---|---|---|
| `json_parse_success` | 输出 JSON 是否可解析 | true |
| `required_section_coverage` | 必填 section 命中数 / 必填 section 总数 | 100% |
| `legacy_schema_violation_count` | 旧 schema 字段出现次数 | 0 |
| `reference_error_count` | 非法引用数量 | 0 |
| `goal_requirement_coverage` | 用户目标关键需求覆盖率 | 基础 case 100%，复杂 case >= 90% |
| `event_chain_completeness` | 关键事件链路是否闭合 | 关键链路必须闭合 |
| `state_model_coverage` | 必需状态变量覆盖率 | >= 90% |
| `policy_selection_accuracy` | 期望策略命中率 | >= 90% |
| `completion_condition_accuracy` | 完成条件是否准确且可判定 | true |

### 8.2 全量 benchmark 指标

| 指标 | 含义 |
|---|---|
| `pass_rate` | 所有 case 中通过的比例。 |
| `positive_case_pass_rate` | 正向 case 通过率。 |
| `negative_case_handling_rate` | 负向 case 正确报告问题或拒绝硬编的比例。 |
| `average_goal_requirement_coverage` | 用户目标覆盖度平均值。 |
| `average_semantic_coverage` | 语义断言平均覆盖率。 |
| `hallucination_rate` | 幻觉设备、行为、信号、状态出现比例。 |
| `legacy_schema_violation_rate` | 旧 schema 污染比例。 |

---

## 9. 后续落地任务

| 优先级 | 任务 | 产物 |
|---|---|---|
| P0 | 定义统一 `test_assertions.json` schema | `docs/test/case/test_assertions.schema.json` |
| P0 | 为已有 9 个 case 补齐最终图断言 | 各 `scene_XX/test_assertions.json` |
| P0 | 实现最终图 assertion runner | `agent/scene_behavior_agent/tests/run_case_assertions.py` |
| P1 | 为每个 case 补输入 JSON | `scene_document.input.json`、`device_specs.input.json` |
| P1 | 为关键 case 补语义 golden | `scene_behavior_graph.golden.json` |
| P1 | 输出 per-case report | `validation_report.md` |
| P2 | 汇总 benchmark 指标 | `benchmark_summary.md` |

---

## 10. 一句话结论

`SceneBehaviorGraph Agent` 的验证应收敛为 **最终图合规性验证 + 最终图语义准确性验证**。

中间节点和工具结果用于 debug，但不作为主要判卷对象；真正需要验证的是最终 `SceneBehaviorGraph` 是否结构合规，并且是否把用户目标、场景事实、设备能力、事件路由、状态模型、行为规则、状态迁移和策略函数准确表达出来。
