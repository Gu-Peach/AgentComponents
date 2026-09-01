# SceneBehaviorGraph Agent Tools

`tools/` 是 `SceneBehaviorGraph` Agent 的确定性工具层。它只负责读取事实、建立索引、执行校验、提供策略模板、组装结果和渲染解释；不在工具内部让 LLM 隐式生成完整行为图。

在 LangGraph 中，这些工具主要被 Tool Node 或 Model+Tool Node 调用，为模型节点提供可验证的输入和输出边界。

## 1. 设计边界

| 原则 | 说明 |
|---|---|
| 工具确定性 | 同样输入应得到同样输出，便于测试、回放和审计。 |
| 工具不替代 Agent 推理 | 工具可以整理事实、校验引用、返回模板，但不负责语义推理和行为图创作。 |
| 工具不替代 Runtime | 工具不执行仿真、不维护高频状态、不做实时调度。 |
| LLM 不直接写最终结果 | LLM 生成草案字段，最终由 `SceneBehaviorGraphWriter` 组装并写入。 |
| Validator 是入库门禁 | `GraphValidator` 校验通过后，行为图才允许进入 finalize 阶段。 |

## 2. 工具总览

| 工具类 | 文件 | 主要调用节点 | 核心方法 | 作用 |
|---|---|---|---|---|
| `SceneReader` | `scene_reader.py` | `load_scene` | `read()` | 读取并规范化 `SceneDocument`，提取场景事实和设备规范引用。 |
| `DeviceSpecReader` | `device_spec_reader.py` | `load_device_specs` | `read_many()` | 根据场景中的 `spec_id` 读取设备本体规范，并建立行为、信号、资源索引。 |
| `ConnectionValidator` | `connection_validator.py` | `validate_connections` | `validate()` | 在正式建模前校验 `SceneDocument` 显式连接是否引用有效。 |
| `GraphValidator` | `graph_validator.py` | `validate_connections`、`validate_graph` | `validate()`、`validate_connections()` | 校验 `SceneBehaviorGraph` 草案的完整性、引用关系、事件路由和行为规则。 |
| `PolicyLibrary` | `policy_library.py` | `synthesize_policies` | `default_policies()`、`infer_policies()` | 提供可复用策略模板，并根据场景事实推断应启用的策略草案。 |
| `SceneBehaviorGraphWriter` | `writer.py` | `assemble_graph`、`finalize` | `assemble()`、`write()` | 把 AgentState 草案字段组装成完整 `SceneBehaviorGraph`，并写入 JSON。 |
| `ExplanationRenderer` | `explanation_renderer.py` | `explain` | `render()` | 将行为图草案、模块和校验状态渲染成用户可读解释。 |

## 3. SceneReader

`SceneReader` 负责把输入的场景文件转换成 Agent 可直接消费的 `scene_facts`。

| 项 | 说明 |
|---|---|
| 文件 | `scene_reader.py` |
| 调用节点 | `load_scene` |
| 输入 | `scene_document_ref`，可以是 `SceneDocument` JSON 路径，也可以是包含 `scene_document` 包装层的 demo JSON。 |
| 输出 | 标准化后的 `scene_facts`。 |

### 输出字段

| 字段 | 含义 |
|---|---|
| `raw` | 原始 `SceneDocument` 内容，供后续节点保留完整事实。 |
| `scene_id` | 场景 ID；若输入缺失则回退到 `unknown_scene`。 |
| `scene_revision` | 场景版本，用于避免基于旧场景生成行为图。 |
| `instances` | 场景中的设备实例列表。 |
| `materials` | 场景中的物料实例列表。 |
| `physical_edges` | 场景物理连接关系。 |
| `process_edges` | 场景工艺流程连接关系。 |
| `signal_edges` | 场景信号连接关系。 |
| `device_spec_refs` | 从 `instances[].spec_id` 提取并去重后的设备规范 ID 列表。 |
| `instance_index` | 以 `instance_id` 为 key 的设备实例索引，供校验器快速查找。 |
| `material_index` | 以 `material_id` 为 key 的物料索引，供行为建模和策略生成使用。 |

### 使用位置

```text
scene_document_ref
  -> SceneReader.read()
  -> AgentState.scene_facts
  -> AgentState.device_spec_refs
```

## 4. DeviceSpecReader

`DeviceSpecReader` 负责读取场景实际引用到的设备本体规范，即 `DeviceSpec`。

| 项 | 说明 |
|---|---|
| 文件 | `device_spec_reader.py` |
| 调用节点 | `load_device_specs` |
| 输入 | `device_spec_refs`，来自 `SceneReader` 提取的 `spec_id` 列表。 |
| 输出 | `device_capabilities`，包含原始设备规范、缺失项和多个能力索引。 |

### 查找逻辑

`DeviceSpecReader` 默认从 `docs/business/SimulationSchema/1.DeviceSpec` 下递归查找设备 JSON：

1. 优先匹配文件名 `{spec_id}.json`。
2. 如果文件名未命中，则遍历设备 JSON，匹配 `device_spec_id` 或 `id`。
3. 自动跳过 `schema.json`、`template.json`、`common_device_spec.schema.json`、`example.json` 等规范文件。

### 输出字段

| 字段 | 含义 |
|---|---|
| `specs` | 读取到的设备规范字典，key 为规范化后的设备 ID。 |
| `missing` | 未找到的 `spec_id` 列表，后续由连接校验报告为错误。 |
| `behavior_index` | 每类设备可用 `transport_behaviors[].behavior_id` 索引。 |
| `signal_port_index` | 每类设备可用 `signal_ports[].port_id` 索引。 |
| `resource_index` | 每类设备声明的资源索引，来源包括 `runtime_contract.resources` 和行为级 `resources`。 |
| `summary` | 设备类型、行为、信号和默认状态的轻量摘要，供模型节点理解能力边界。 |

### 能力边界

`DeviceSpecReader` 只回答“设备本体能做什么”，不回答“本场景应该怎么协作”。场景级协作关系由 `SceneBehaviorGraph` 表达。

## 5. ConnectionValidator

`ConnectionValidator` 是 `GraphValidator.validate_connections()` 的轻量包装，用于建模开始前的显式连接预检。

| 项 | 说明 |
|---|---|
| 文件 | `connection_validator.py` |
| 调用节点 | `validate_connections` |
| 输入 | `scene_facts`、`device_capabilities`。 |
| 输出 | `connection_validation`，结构为 `{ valid, issues }`。 |

### 当前校验范围

| 校验项 | 说明 |
|---|---|
| 设备规范是否缺失 | `device_capabilities.missing` 中的每个规范都会生成 `missing_device_spec` 错误。 |
| 信号端点格式 | `signal_edges[].source/target` 必须使用 `instance_id.port_id` 格式。 |
| 信号端点实例是否存在 | `instance_id` 必须存在于 `SceneDocument.instances`。 |
| 信号端口是否存在 | `port_id` 应存在于对应 `DeviceSpec.signal_ports`；不存在时当前返回 warning。 |

### 分支影响

```text
connection_validation.valid == true
  -> understand_scene

connection_validation.valid == false
  -> explain
  -> human_review
```

## 6. GraphValidator

`GraphValidator` 是行为图入库前的强制校验工具，负责检查 `SceneBehaviorGraph` 草案是否可以被 Runtime 消费。

| 项 | 说明 |
|---|---|
| 文件 | `graph_validator.py` |
| 调用节点 | `validate_graph`，也被 `ConnectionValidator` 复用。 |
| 输入 | `scene_behavior_graph_draft`、`scene_facts`、`device_capabilities`。 |
| 输出 | `validation_report`，结构为 `{ valid, issues }`。 |

### 必需一级板块

`GraphValidator` 会检查以下 `SceneBehaviorGraph` 一级字段是否存在：

| 字段 | 作用 |
|---|---|
| `goal` | 用户目标和工艺意图。 |
| `modules` | 工艺模块划分。 |
| `event_bus` | 场景级事件、topic、订阅和路由定义。 |
| `state_model` | RuntimeSnapshot 需要维护的状态变量定义。 |
| `behavior_rules` | `trigger / guard / policy / action` 行为规则。 |
| `state_transition_rules` | 行为开始、完成、异常后的状态更新规则。 |
| `policies` | 策略类型和参数定义。 |
| `completion_conditions` | 仿真成功结束条件。 |
| `failure_observations` | 死锁、超时、资源冲突等异常观测条件。 |

### 事件总线校验

| 校验项 | 说明 |
|---|---|
| `routes[].from` | 必须引用 `event_bus.events[].event_id` 中存在的事件。 |
| topic 目标 | `routes[].to.type == "topic"` 时，`to.id` 必须存在于 `event_bus.topics`。 |
| topic 订阅 | 被路由到的 topic 必须存在对应 `subscriptions[topic_id]`。 |
| 未订阅 topic | 已注册但无订阅的 topic 返回 warning，提示可能未使用。 |

### 行为规则校验

| 校验项 | 说明 |
|---|---|
| trigger 事件 | `behavior_rules[].trigger.event_id` 必须存在于已注册事件，或 topic subscription 展开的 `message_event_id`。 |
| action 实例 | 固定 `instance_id` 必须存在于 `SceneDocument.instances`；`trigger.*` 和 `policy.*` 动态引用允许通过。 |
| action 行为 | 固定 `behavior_id` 必须存在于对应 `DeviceSpec.transport_behaviors`。 |
| target 歧义 | 如果 `action.target` 指向另一个 `rule_id`，返回 warning，提示目标语义可能含混。 |

### 状态迁移校验

| 校验项 | 说明 |
|---|---|
| emit 事件 | `state_transition_rules[].effects` 中 `emit xxx` 的事件应在 `event_bus.events` 中注册。 |
| observation 事件 | `observation.*` 允许作为异常观测事件前缀，不强制注册为普通事件。 |

## 7. PolicyLibrary

`PolicyLibrary` 提供可复用的策略定义模板。它输出的是结构化策略草案，不是可执行 Python 函数；Runtime 侧仍需要有可信的 `PolicyLibrary` 实现来执行这些策略。

| 项 | 说明 |
|---|---|
| 文件 | `policy_library.py` |
| 调用节点 | `synthesize_policies` |
| 输入 | `scene_facts`、`process_modules`。 |
| 输出 | `policies_draft`。 |

### 默认策略

| 策略 | 含义 |
|---|---|
| `deterministic_priority` | 当多个规则同时可执行时，使用确定性优先级和字典序 tie breaker，保证仿真可复现。 |
| `resource_lock` | 对设备资源或共享资源加锁，冲突时进入等待。 |
| `deadlock_detection` | 当没有可执行行为且完成条件未满足时，发出 `observation.deadlock_detected`。 |

### 推断策略

| 触发条件 | 输出策略 | 说明 |
|---|---|---|
| 场景存在物料且机械臂数量大于 1 | `claim_workpiece` | 使用 `shared_pool_claim`，避免多个机械臂抢同一物料。 |
| 场景中传送带数量大于 1 | `backpressure` | 使用 `capacity_threshold`，表达下游满载、阻塞和恢复。 |
| 策略合成节点固定补充 | `target_conveyor_selection` | 使用 `load_balancing`，选择负载较低且未阻塞的出料传送带。 |

## 8. SceneBehaviorGraphWriter

`SceneBehaviorGraphWriter` 负责把分散在 `AgentState` 里的草案字段组装成完整 `SceneBehaviorGraph`，并在 finalize 阶段写入文件。

| 项 | 说明 |
|---|---|
| 文件 | `writer.py` |
| 调用节点 | `assemble_graph`、`finalize` |
| 输入 | `AgentState` 或最终 `SceneBehaviorGraph`。 |
| 输出 | `scene_behavior_graph_draft`、`final_scene_behavior_graph` 或 JSON 文件。 |

### assemble 输出结构

| 字段 | 来源 |
|---|---|
| `schema_id` | 根据 `scene_id` 生成。 |
| `schema_type` | 固定为 `SceneBehaviorGraph`。 |
| `version` | 当前实现为 `0.2.0`。 |
| `source.kind` | 固定为 `langgraph_agent_generated`。 |
| `source.agent_run_id` | 来自 `AgentState.run_id`。 |
| `goal` | 来自 `AgentState.intent`。 |
| `modules` | 来自 `AgentState.process_modules`。 |
| `event_bus` | 来自 `AgentState.event_bus_draft`。 |
| `state_model` | 来自 `AgentState.state_model_draft`。 |
| `behavior_rules` | 来自 `AgentState.behavior_rules_draft`。 |
| `state_transition_rules` | 来自 `AgentState.state_transition_rules_draft`。 |
| `policies` | 来自 `AgentState.policies_draft`。 |
| `completion_conditions` | 来自 `AgentState.completion_conditions_draft`。 |
| `failure_observations` | 来自 `AgentState.failure_observations_draft`。 |

### write 行为

`write(output_path, graph)` 会把最终行为图写入指定 JSON 路径。当前本地默认输出目录来自 `AgentConfig.default_output_dir`。

## 9. ExplanationRenderer

`ExplanationRenderer` 负责把结构化行为图草案转换成用户可读的说明文本。

| 项 | 说明 |
|---|---|
| 文件 | `explanation_renderer.py` |
| 调用节点 | `explain` |
| 输入 | `AgentState`。 |
| 输出 | `explanation` 字符串。 |

### 当前解释内容

| 内容 | 说明 |
|---|---|
| 模块划分 | 从 `process_modules[].module_id` 汇总。 |
| 事件路由数量 | 从 `event_bus_draft.routes` 统计。 |
| 主链路说明 | 描述从 `runtime.sim_start` 到托盘运输、机械臂拣选的主事件链。 |
| backpressure 说明 | 描述下游阻塞和恢复事件如何影响行为规则。 |
| 校验状态 | 根据 `validation_report.valid` 或 `connection_validation.valid` 输出是否通过。 |

## 10. 导出入口

`__init__.py` 统一导出工具类，方便节点模块按稳定入口导入：

```python
from agent.scene_behavior_agent.tools import (
    ConnectionValidator,
    DeviceSpecReader,
    ExplanationRenderer,
    GraphValidator,
    PolicyLibrary,
    SceneBehaviorGraphWriter,
    SceneReader,
)
```

## 11. 与 LangGraph 节点的关系

```text
load_scene
  -> SceneReader

load_device_specs
  -> DeviceSpecReader

validate_connections
  -> ConnectionValidator
  -> GraphValidator.validate_connections

synthesize_policies
  -> PolicyLibrary

assemble_graph
  -> SceneBehaviorGraphWriter.assemble

validate_graph
  -> GraphValidator.validate

explain
  -> ExplanationRenderer

finalize
  -> SceneBehaviorGraphWriter.write
```

## 12. 后续扩展方向

| 工具 | 可扩展能力 |
|---|---|
| `SceneReader` | 增加数据库读取、版本锁、SceneDocument schema 校验。 |
| `DeviceSpecReader` | 增加设备规范版本选择、缓存、能力摘要裁剪。 |
| `ConnectionValidator` | 扩展物理接口、流程接口、信号接口的类型兼容性校验。 |
| `GraphValidator` | 增加状态变量引用解析、资源锁完整性、completion condition 可判定性校验。 |
| `PolicyLibrary` | 增加 queue wait、timeout retry、capacity backpressure、storage slot selection 等策略模板。 |
| `SceneBehaviorGraphWriter` | 增加持久化到数据库、revision 生成、审计日志。 |
| `ExplanationRenderer` | 增加 Mermaid 预览、事件 trace 预览、论文实验摘要输出。 |
