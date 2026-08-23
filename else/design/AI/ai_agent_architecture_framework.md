# AI 层架构与 Agent 调度框架设计

> 面向微服务架构的 AI 调度层专题设计
> 聚焦 Agent Scheduler、Skill 集成、SimPlan 协议与执行协作

---

## 一、文档目标

本文档用于补充项目 AI 层的专题设计，重点回答以下问题：

- AI 层在整个平台中的职责边界是什么
- Agent 调度部分应该如何拆分
- Skill 应该如何组织、注册、选择与调用
- AI 层如何与仿真执行层协作
- 在微服务架构下，各模块之间建议使用什么通信方式

本文档不替代主设计稿，而是作为 [ai_simulation_agent_design.md](/E:/project/Agentic%20Components/docs/design/AI/ai_simulation_agent_design.md) 的补充说明，偏重“框架层”和“服务协作层”。

---

## 二、AI 层的定位

在本项目中，AI 层不应被设计成“直接控制设备运动的大模型”，而应被设计成“负责任务理解、能力编排、计划生成和交互澄清的智能调度层”。

核心原则如下：

- AI 层负责“决定做什么、按什么顺序做、需要哪些参数、调用哪些能力”
- 仿真执行层负责“根据确定的计划执行事件调度、设备动作和轨迹计算”
- Skill 层负责“提供可复用、可组合、可替换的专业能力”
- AI 层与执行层之间通过结构化协议解耦，协议核心是 `SimPlan`

因此，这个系统的核心不是“LLM 直接驱动仿真”，而是：

`LLM + Agent 状态机/图调度 + Skill 工具体系 + SimPlan 协议 + 确定性执行引擎`

---

## 三、总体分层

推荐将 AI 相关能力划分为 5 层。

### 3.1 交互入口层

负责接收来自前端工作区的 AI 请求，例如：

- 自然语言仿真指令
- 当前项目上下文
- 场景 ID、会话 ID
- 上传的工艺文档、约束文档、附件
- 运行模式、agent 模式、目标指标

这一层通常由前端通过 REST 提交请求，并通过 SSE 或 WebSocket 接收过程性反馈。

### 3.2 Agent 编排层

这是 AI 层的核心，推荐由 `Agent Scheduler` 承担。它的职责是：

- 解析用户意图
- 判断任务复杂度
- 决定是否需要读取场景、分析拓扑、补齐参数
- 决定调用哪些 Skill
- 处理澄清提问
- 生成和修正 `SimPlan`
- 在执行前完成计划校验

这一层不做底层轨迹求解，只做高层编排和决策。

### 3.3 Skill 能力层

Skill 是 Agent 可调度的标准能力单元。Skill 可以是：

- 本地函数
- Python 工具
- 独立微服务的 REST 接口
- gRPC 服务
- MCP 风格工具

Skill 的职责是解决局部问题，而不是承担整体调度。

### 3.4 协议与计划层

这一层负责将自然语言任务转化为结构化计划对象，包括：

- `SimPlan`
- `DevicePlan`
- `CoordinationRule`
- `ExecutionConstraint`
- `ValidationResult`

它是 AI 层与执行层解耦的关键。

### 3.5 仿真执行层

这一层不属于 AI 层本身，但与 AI 层强耦合协作。它负责：

- SimPy 事件调度
- 设备级算法执行
- 轨迹生成
- 资源竞争与等待
- 日志输出
- 动画帧输出
- 仿真指标统计

---

## 四、总体框架图

下面这张图可以作为 AI 层的总览框架图。

```text
┌──────────────────────────────────────────────────────────────────────┐
│                            前端工作区                                │
│ Chat Panel / Scene Context / Project Context / Uploads / Terminal   │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ REST POST
                                v
┌──────────────────────────────────────────────────────────────────────┐
│                        AI Gateway / AI API                           │
│ 接收 messages、projectId、sessionId、附件、agent 参数                 │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                v
┌──────────────────────────────────────────────────────────────────────┐
│                        Agent Scheduler                               │
│ Intent Parser -> Scene Reader -> Topology Analyzer -> Param Resolver │
│ -> Clarifier -> Plan Generator -> Plan Validator -> Executor Handoff │
└───────────────┬──────────────────────┬───────────────────────────────┘
                │                      │
                │ 调度                 │ 调度
                v                      v
┌──────────────────────────┐  ┌───────────────────────────────────────┐
│      Skill Registry      │  │            Session Memory             │
│ skill 元信息 / 路由策略   │  │ 会话状态 / 参数补充 / 计划历史         │
└───────────────┬──────────┘  └───────────────────────────────────────┘
                │
                v
┌──────────────────────────────────────────────────────────────────────┐
│                           Skill Layer                                │
│ read_scene_config / analyze_topology / resolve_device_params         │
│ select_device_algorithm / generate_coordination_rules / doc_parser   │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                v
┌──────────────────────────────────────────────────────────────────────┐
│                            SimPlan                                   │
│ 结构化执行计划：设备、参数、时序、规则、约束、输出要求                │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ REST / Queue
                                v
┌──────────────────────────────────────────────────────────────────────┐
│                    Simulation Runtime Service                        │
│ SimPy Executor + Device Algorithms + Metrics + Frame Stream         │
└───────────────┬────────────────────────────┬─────────────────────────┘
                │                            │
                │ WebSocket                  │ WebSocket / SSE
                v                            v
┌──────────────────────────┐       ┌───────────────────────────────────┐
│      3D Animation        │       │      Terminal / Status Stream     │
│ 位置帧 / 关节帧 / 状态帧   │       │ 计划摘要 / 执行日志 / 指标结果     │
└──────────────────────────┘       └───────────────────────────────────┘
```

---

## 五、Agent Scheduler 的设计

### 5.1 调度器的核心职责

`Agent Scheduler` 不是一个简单的 prompt 调用器，而是一个有状态的编排器。推荐将其理解为“面向业务流程的图调度引擎”。

它至少承担以下职责：

- 根据输入复杂度选择不同处理路径
- 在不同节点间传递统一状态对象
- 按需调用 Skill
- 在信息不足时暂停并向用户追问
- 在计划无效时回退、修正或重试
- 输出结构化 `SimPlan`

### 5.2 推荐状态节点

建议调度器至少包含以下节点：

1. `Intent Parser`
   解析用户自然语言，提取任务目标、时长、设备、限制条件、目标指标。

2. `Scene Reader`
   读取场景定义、设备配置、连接关系、工作流和默认参数。

3. `Topology Analyzer`
   分析设备间的依赖关系、上下游、关键路径和并行组。

4. `Param Resolver`
   将默认参数、用户参数、文档参数和算法要求合并，并检查缺失项。

5. `Clarifier`
   如果关键参数缺失，则生成可理解的追问。

6. `Plan Generator`
   结合意图、场景、拓扑和参数，生成结构化 `SimPlan`。

7. `Plan Validator`
   校验计划是否完整、合法、无明显冲突。

8. `Executor Handoff`
   将计划提交给仿真执行层。

### 5.3 调度状态机

```text
用户请求
   |
   v
[Intent Parser]
   |
   +--> 输入复杂度判断：simple / medium / detailed
   |
   v
[Scene Reader]
   |
   v
[Topology Analyzer]
   |
   v
[Param Resolver]
   |
   +--> 参数缺失 ------> [Clarifier] ------> 用户补充 ------+
   |                                                      |
   +------------------------------------------------------+
   |
   v
[Plan Generator]
   |
   v
[Plan Validator]
   |
   +--> 校验失败 --> [Fix / Replan] --> 回到 Plan Generator
   |
   v
[Executor Handoff]
   |
   v
Simulation Runtime
```

### 5.4 为什么要用图调度而不是单次 LLM 调用

如果只做一次模型调用，会有几个明显问题：

- 输入上下文过大，容易失控
- 缺参数时无法自然停下来追问
- 计划不可验证、不可修复
- 无法灵活插入 Skill
- 无法做复杂多轮调度

而图调度的优势在于：

- 每一步职责明确
- 节点可以替换和扩展
- 支持失败回退
- 支持人机协作补参
- 方便微服务拆分

---

## 六、基于 LangGraph 的 Agent 架构设计图

这一节专门回答“Agent 在 LangGraph 里到底怎么组织”。

如果从 LangGraph 的视角看，这个 Agent 不是一个线性流程，而是由以下几个核心元素构成：

- `State`
  整个图中流转的统一状态对象，例如 `messages`、`intent`、`scene_doc`、`topology`、`resolved_params`、`sim_plan`。

- `Node`
  每个节点负责一个明确步骤，例如意图解析、场景读取、参数补齐、计划生成。

- `Conditional Edge`
  根据当前状态判断下一步走向，例如参数是否缺失、计划是否通过校验。

- `ToolNode`
  用于承载 Skill 调用，把 `read_scene_config`、`analyze_topology` 等能力接入图中。

- `Memory / Checkpoint`
  保存会话上下文、中间状态、重试点和补问记录。

- `Human-in-the-loop`
  当关键参数缺失时，图不会盲目前进，而是暂停到澄清节点，等待用户反馈后继续执行。

### 6.1 LangGraph 视角下的内部架构图

```text
┌────────────────────────────────────────────────────────────────────┐
│                      LangGraph Agent Runtime                       │
└────────────────────────────────────────────────────────────────────┘

        ┌──────────────────────────────────────────────────────┐
        │                     Agent State                      │
        │ messages / intent / scene_doc / topology / params   │
        │ sim_plan / validation_errors / pending_questions    │
        └───────────────┬──────────────────────────────────────┘
                        │
                        v
              ┌──────────────────────┐
              │      START Node      │
              └──────────┬───────────┘
                         │
                         v
              ┌──────────────────────┐
              │    Intent Parser     │
              │ LLMNode: 提取意图     │
              └──────────┬───────────┘
                         │
                         v
              ┌──────────────────────┐
              │    Route Decision     │
              │ Conditional Edge      │
              │ simple/medium/detailed│
              └──────────┬───────────┘
                         │
                         v
              ┌──────────────────────┐
              │     Scene Reader     │
              │ ToolNode / Skill     │
              └──────────┬───────────┘
                         │
                         v
              ┌──────────────────────┐
              │  Topology Analyzer   │
              │ ToolNode / Skill     │
              └──────────┬───────────┘
                         │
                         v
              ┌──────────────────────┐
              │   Param Resolver     │
              │ ToolNode + LLMNode   │
              └──────────┬───────────┘
                         │
             ┌───────────┴────────────┐
             │                        │
             v                        v
┌──────────────────────┐    ┌─────────────────────────┐
│ Missing Param Branch │    │ Params Complete Branch  │
│ Conditional Edge     │    │ Conditional Edge        │
└──────────┬───────────┘    └──────────┬──────────────┘
           │                           │
           v                           v
┌──────────────────────┐    ┌─────────────────────────┐
│      Clarifier       │    │    Plan Generator       │
│ LLMNode: 追问用户     │    │ LLMNode: 生成 SimPlan   │
└──────────┬───────────┘    └──────────┬──────────────┘
           │                           │
           │ Human Feedback            v
           │                 ┌─────────────────────────┐
           └────────────────>│    Plan Validator       │
                             │ ToolNode / Rule Check   │
                             └──────────┬──────────────┘
                                        │
                         ┌──────────────┴──────────────┐
                         │                             │
                         v                             v
             ┌─────────────────────────┐   ┌─────────────────────────┐
             │ Validation Failed       │   │ Validation Passed       │
             │ Conditional Edge        │   │ Conditional Edge        │
             └──────────┬──────────────┘   └──────────┬──────────────┘
                        │                             │
                        v                             v
             ┌─────────────────────────┐   ┌─────────────────────────┐
             │    Fix / Replan Node    │   │   Executor Handoff      │
             │ LLMNode / Retry Node    │   │ Submit SimPlan          │
             └──────────┬──────────────┘   └──────────┬──────────────┘
                        │                             │
                        └──────────────┬──────────────┘
                                       │
                                       v
                              ┌──────────────────────┐
                              │       END Node       │
                              └──────────────────────┘


           ┌─────────────────────────── Supporting Components ───────────────────────────┐
           │                                                                              │
           │  Checkpointer / MemorySaver                                                  │
           │  - 保存 AgentState 快照                                                       │
           │  - 支持中断恢复                                                               │
           │  - 支持多轮对话延续                                                           │
           │                                                                              │
           │  Tool Registry                                                               │
           │  - read_scene_config                                                         │
           │  - analyze_topology                                                          │
           │  - resolve_device_params                                                     │
           │  - select_device_algorithm                                                   │
           │  - generate_coordination_rules                                               │
           │                                                                              │
           └──────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 LangGraph 组件和项目模块的映射关系

为了避免把 LangGraph 仅仅理解成“几个节点串起来”，这里可以再对应一下：

| LangGraph 概念 | 在本项目中的角色 |
|---|---|
| `StateGraph` | 仿真调度 Agent 的主流程图 |
| `State` | `SimAgentState`，承载整个调度上下文 |
| `LLMNode` | 意图解析、澄清追问、计划生成、重规划 |
| `ToolNode` | Skill 调用层 |
| `Conditional Edge` | 根据参数完整性、校验结果决定分支 |
| `Checkpointer` | 多轮对话恢复、重试恢复、执行前状态保存 |
| `Interrupt / Human-in-the-loop` | 参数缺失时暂停，等待用户补充 |
| `END` | 输出 `SimPlan` 或提交执行任务 |

### 6.3 这个图里最关键的设计点

这张基于 LangGraph 的图里，最关键的是以下几件事：

- LLM 只负责“理解、追问、规划、修正”，不直接做底层执行。
- ToolNode 承载 Skill，让能力调用变成图中的标准节点，而不是散落在 prompt 里。
- Conditional Edge 让 Agent 有真正的“分支逻辑”，而不是一条直线跑到底。
- Clarifier 节点把“缺参数时向用户追问”正式纳入图结构，而不是额外补丁逻辑。
- Plan Validator 和 Fix/Replan 构成闭环，让计划具备可修复性。
- Checkpointer 让 LangGraph 可以支持多轮对话、失败恢复和长链路任务。

### 6.4 如果落到代码层，推荐的 LangGraph 组装方式

推荐的实现思路如下：

```text
StateGraph(SimAgentState)
  -> add_node("intent_parser", intent_parser_node)
  -> add_node("scene_reader", tool_node(scene_tools))
  -> add_node("topology_analyzer", tool_node(topology_tools))
  -> add_node("param_resolver", param_resolver_node)
  -> add_node("clarifier", clarifier_node)
  -> add_node("plan_generator", plan_generator_node)
  -> add_node("plan_validator", validator_node)
  -> add_node("fix_replan", fix_replan_node)
  -> add_node("executor_handoff", executor_handoff_node)

  -> add_conditional_edges(...)
  -> compile(checkpointer=MemorySaver or RedisCheckpointer)
```

也就是说，这里的重点不是“LangGraph 能不能用”，而是：

**这个项目的 Agent 调度天然就适合用 LangGraph 来表达。**

因为它本身就有：

- 明确状态
- 多节点流程
- 条件分支
- Tool 调用
- 用户补问
- 失败重试
- 长任务恢复

---

## 七、Skill 体系怎么设计

### 6.1 Skill 的本质

Skill 不是“第二个 Agent”，而是 Agent 可以调度的专业能力模块。

更准确地说：

- Agent 负责决策与编排
- Skill 负责提供原子化专业能力

Skill 最好被设计成“结构化能力单元”，而不是零散函数集合。

### 6.2 Skill 的元信息模型

建议每个 Skill 至少包含以下元信息：

```text
name: 技能名称
description: 技能说明
input_schema: 输入结构
output_schema: 输出结构
preconditions: 前置条件
side_effects: 是否有副作用
timeout: 超时时间
retry_policy: 重试策略
service_target: 调用目标
protocol: REST / gRPC / local / MCP
```

例如：

```text
Skill: analyze_topology
description: 分析场景设备拓扑与执行顺序
input_schema: { projectId, topology, workflow }
output_schema: { executionOrder, parallelGroups, criticalPath }
preconditions: 场景已加载
service_target: topology-service
protocol: REST
```

### 6.3 Skill 的分层

建议将 Skill 分成三类：

1. 场景理解类
   例如 `read_scene_config`、`read_device_specs`、`parse_uploaded_doc`

2. 规划生成类
   例如 `analyze_topology`、`resolve_device_params`、`select_device_algorithm`

3. 协同执行类
   例如 `generate_coordination_rules`、`estimate_bottleneck`、`validate_constraints`

### 6.4 推荐的 Skill 组织结构

```text
AI Service
 ├─ Agent Scheduler
 ├─ Skill Registry
 ├─ Skill Selector
 ├─ Skill Executor
 └─ Session Memory

Skill Services
 ├─ Scene Skill Service
 ├─ Topology Skill Service
 ├─ Param Skill Service
 ├─ Algorithm Skill Service
 └─ Rule Generation Skill Service
```

### 6.5 Skill 调度流程

```text
Agent 当前节点判断需要什么能力
        |
        v
从 Skill Registry 检索候选 Skill
        |
        v
Skill Selector 选择合适实现
        |
        v
Skill Executor 发起调用
        |
        v
返回结构化结果给 Agent State
        |
        v
Agent 继续推进下一节点
```

### 6.6 为什么 Skill 体系适合微服务

因为后续你们的平台不会只有一个 Agent，而会出现：

- 仿真调度 Agent
- 场景构建 Agent
- 工艺分析 Agent
- 优化建议 Agent
- 故障诊断 Agent

如果没有 Skill 体系，每个 Agent 都会重复实现“读场景”“读拓扑”“查设备参数”等能力，导致明显的冗余和脆弱性。Skill 化之后，这些能力就可以复用。

---

## 八、Skill 与 Agent 的协作框架图

这张图专门说明“Agent 调度”和“Skill 工具体系”的关系。

```text
┌──────────────────────────┐
│      用户自然语言请求     │
└─────────────┬────────────┘
              │
              v
┌──────────────────────────┐
│     Agent Scheduler      │
│ 判断当前状态与下一动作    │
└───────┬────────┬─────────┘
        │        │
        │        └──────────────────────────────┐
        │                                       │
        v                                       v
┌──────────────────────┐            ┌─────────────────────────┐
│    Skill Registry    │            │     Session Memory      │
│ 有哪些 Skill 可用     │            │ 参数、补问、历史计划     │
└──────────┬───────────┘            └─────────────────────────┘
           │
           v
┌──────────────────────┐
│    Skill Selector    │
│ 当前任务该用哪个实现  │
└──────────┬───────────┘
           │
           v
┌──────────────────────┐
│    Skill Executor    │
│ 发起 local / REST 调用│
└──────────┬───────────┘
           │
           v
┌──────────────────────────────────────────────┐
│ Skills                                        │
│ - read_scene_config                           │
│ - analyze_topology                            │
│ - resolve_device_params                       │
│ - select_device_algorithm                     │
│ - generate_coordination_rules                 │
│ - validate_sim_plan                           │
└──────────┬───────────────────────────────────┘
           │
           v
┌──────────────────────────┐
│  结构化结果写回 AgentState │
└─────────────┬────────────┘
              │
              v
┌──────────────────────────┐
│   Plan Generator / Next   │
└──────────────────────────┘
```

---

## 九、SimPlan 为什么是关键中间层

### 8.1 SimPlan 的角色

`SimPlan` 是 AI 层与执行层之间最重要的协议对象。

它的作用是把：

- 自然语言任务
- 场景上下文
- 文档约束
- 算法选择
- 协调规则

统一转换成可执行、可校验、可追踪的结构化计划。

### 8.2 SimPlan 应该至少包含什么

建议 `SimPlan` 至少包含：

- 计划版本
- 场景 ID / 项目 ID
- 全局仿真配置
- 设备计划列表
- 协调规则
- 资源约束
- 执行优先级
- 输出要求
- 计划摘要

### 8.3 SimPlan 的价值

`SimPlan` 的价值主要体现在四点：

- 解耦：AI 层与仿真层可以独立演进
- 可验证：计划可以先验校验，再进入执行
- 可追踪：方便定位问题出在理解、规划还是执行
- 可复用：后续可以沉淀为模板或方案版本

---

## 十、一次完整请求的协作流程

下面用一个典型请求说明整条链路如何工作。

示例请求：

`让焊接单元和传送带联动跑 1 小时，传送带速度 400mm/s。`

处理流程如下：

1. 前端将 `messages`、`projectId`、`sessionId` 提交给 AI API。
2. Agent Scheduler 进入 `Intent Parser`，识别这是一个“多设备联动仿真”请求。
3. 调用 `read_scene_config` 获取焊接单元、传送带、连接关系和默认参数。
4. 调用 `analyze_topology` 判断传送带是上游、焊接单元是下游，并存在到位触发关系。
5. 调用 `resolve_device_params` 合并用户速度参数和默认工艺参数。
6. 如果焊接节拍、缓存区上限等关键参数缺失，则进入 `Clarifier` 追问用户。
7. 调用 `select_device_algorithm` 为不同设备选择合适算法。
8. 调用 `generate_coordination_rules` 生成信号触发、互锁和等待规则。
9. `Plan Generator` 生成完整 `SimPlan`。
10. `Plan Validator` 校验计划合法性。
11. 计划通过后，提交给仿真执行服务。
12. 执行服务输出日志流和动画帧流，前端实时展示。

---

## 十一、微服务拆分建议

结合项目的微服务架构，建议将 AI 相关服务拆成以下几个模块。

### 10.1 AI Gateway / AI API

职责：

- 接收前端 AI 请求
- 统一鉴权
- 转发给 Agent 调度器
- 向前端输出流式进度

协议建议：

- 前端到 AI Gateway：REST + SSE
- 如果后续需要更强双向交互，可补充 WebSocket

### 10.2 Agent Orchestrator Service

职责：

- 维护 Agent 状态机
- 驱动图调度
- 管理会话状态
- 组装 `SimPlan`

协议建议：

- 与 Skill 服务：REST 为主，内部高频调用可升级到 gRPC
- 与 Memory/State Store：Redis + 数据库

### 10.3 Skill Services

职责：

- 提供可复用能力
- 封装场景读取、拓扑分析、参数解析、规则生成等逻辑

协议建议：

- 内部调用优先 REST
- 高性能结构化调用可以采用 gRPC
- 长耗时任务可走消息队列

### 10.4 Simulation Runtime Service

职责：

- 执行 `SimPlan`
- 调用 SimPy 与设备算法
- 输出帧流、日志流和统计指标

协议建议：

- AI 到 Runtime：REST 提交任务或消息队列投递
- Runtime 到前端：WebSocket 推送帧流与执行状态
- Runtime 到日志/状态系统：Redis Pub/Sub 或消息总线

---

## 十二、协议建议

下面给出一个推荐的通信方式表。

| 通信链路 | 推荐方式 | 原因 |
|---|---|---|
| 前端 -> AI API | REST POST | 需要携带 messages、projectId、sessionId、附件信息 |
| AI API -> 前端文本进度 | SSE | 适合单向流式文本输出 |
| 前端 -> Runtime 状态展示 | WebSocket | 适合实时帧数据和状态更新 |
| Agent Orchestrator -> Skill Service | REST / gRPC | 结构化请求，便于服务拆分 |
| Agent Orchestrator -> Runtime | REST / Queue | 可同步触发或异步派发执行 |
| Runtime -> 日志/事件系统 | Redis Pub/Sub | 便于解耦日志和状态分发 |
| Runtime -> 长任务队列 | Celery / MQ | 适合异步调度执行 |
| 服务 -> 数据库 | PostgreSQL / MongoDB | 分别存储结构化业务数据和文档型配置 |

### 11.1 为什么前端到 AI API 更适合 REST POST

因为未来 AI 请求不只是简单聊天，而是会携带：

- `messages`
- `projectId`
- `sessionId`
- 当前选中设备
- 上传附件
- agent 模式
- 仿真模式
- 中断信号

这些都更适合放在 `POST` 请求体中。

### 11.2 为什么 AI 输出适合 SSE

因为 AI 返回内容天然是单向增量文本流，例如：

- 当前分析步骤
- 补参提示
- 计划摘要
- 执行准备状态

SSE 对这类“服务端持续推送文本事件”的场景非常合适。

### 11.3 为什么执行层更适合 WebSocket

执行层往往需要传输：

- 高频状态更新
- 设备位置帧
- 动画控制消息
- 任务暂停/继续/停止事件

这类消息更适合 WebSocket，而不是 SSE。

---

## 十三、后续可扩展方向

为了支撑平台最终“对标 Visual Components”的目标，AI 层后续建议沿以下方向演进：

### 12.1 多 Agent 协作

未来可以从单一调度 Agent 演进为：

- Simulation Planner Agent
- Process Analyst Agent
- Optimization Agent
- Scene Builder Agent
- Fault Diagnosis Agent

它们共享 Skill 体系和状态协议。

### 12.2 Skill Marketplace

将 Skill 从内部函数发展为可注册、可配置、可替换的能力市场，例如：

- 算法 Skill
- 工艺 Skill
- 规则 Skill
- 报表 Skill

### 12.3 Plan Versioning

让 `SimPlan` 支持版本管理、回放、方案对比和实验记录。

### 12.4 Human-in-the-loop

对于关键场景，允许用户在以下阶段介入：

- 参数确认
- 计划确认
- 执行前审批
- 执行后对比分析

---

## 十四、结论

这个项目的 AI 层最合理的设计，不是“让大模型直接控制工业仿真”，而是：

- 让 Agent 做高层任务编排
- 让 Skill 提供专业能力
- 让 `SimPlan` 成为稳定的中间协议
- 让 SimPy 和设备算法承担确定性执行

从工程角度看，这种设计同时满足：

- 可扩展
- 可验证
- 可微服务拆分
- 可逐步演进到多 Agent 平台

这也更符合项目最终实现“基于大模型的仿真调度与执行平台”的目标。
