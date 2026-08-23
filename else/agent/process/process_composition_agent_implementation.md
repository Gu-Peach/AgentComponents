# 工艺流程编排 Agent 实现说明

## 1. 文档目的

本文档说明当前仓库中“工艺流程编排 Agent”的真实实现方式，不再停留在抽象方案层，而是直接解释：

- Agent 的输入输出规范如何设计
- 身份定义层如何落地
- 感知层、规划层、工具层、行动层如何在代码中实现
- 前后端如何协同完成追问、提案、审批、修改
- 系统如何形成 `感知 → 决策 → 行动 → 反馈` 的闭环

本文档对应的设计方案文档为：

- [process_composition_agent_design.md](E:/project/Agentic%20Components/docs/process/process_composition_agent_design.md)
- [scene_layout_protocol.md](E:/project/Agentic%20Components/docs/process/scene_layout_protocol.md)

## 2. 当前 Agent 的系统定位

当前系统中，工艺流程编排 Agent 是场景编排链路中的第一个 Agent，职责是：

1. 接收用户对“工艺流程编排”的自然语言要求
2. 读取当前前端场景导出的 `Scene Layout JSON`
3. 基于设备基础信息生成 `processFlow.connections`
4. 在信息不足时先向用户追问
5. 在得到足够信息后输出可审阅的流程提案
6. 接受用户批准或修改后继续编排

它不负责：

- 执行层接口推理
- 机械臂 IK 轨迹
- 仿真段生成
- 仿真执行控制

这些能力属于后续仿真规划 Agent 与执行链路。

## 3. Agent 规范如何设计

### 3.1 输入规范

当前编排 Agent 的输入由两部分组成：

1. 用户消息
2. 场景结构化上下文

后端请求模型定义在 [backend/schemas/agent.py](E:/project/Agentic%20Components/backend/schemas/agent.py)，核心字段为：

- `message`: 当前用户输入
- `messages`: 最近对话历史
- `scene_layout`: 当前前端导出的场景布局 JSON

前端在 [frontend/components/ai-chat/streamChat.ts](E:/project/Agentic%20Components/frontend/components/ai-chat/streamChat.ts) 中发送这些字段，Next.js 代理层在 [frontend/app/api/agent/stream/route.ts](E:/project/Agentic%20Components/frontend/app/api/agent/stream/route.ts) 中转发到后端 `/api/agent/stream`。

### 3.2 场景规范

前端导出逻辑在 [frontend/lib/process/sceneLayout.ts](E:/project/Agentic%20Components/frontend/lib/process/sceneLayout.ts)。

虽然完整 `Scene Layout JSON` 包含 `layout / processFlow / simulation` 三部分，但当前编排 Agent 实际只消费：

- 设备 `id`
- 设备 `name`
- 设备 `type`
- 设备 `transform.position`
- 当前已有的 `processFlow.connections`

这意味着编排 Agent 的输入边界非常明确：它只处理流程层信息，不读取执行层接口。

### 3.3 输出规范

当前编排 Agent 的标准输出类型定义在 [frontend/types/process.ts](E:/project/Agentic%20Components/frontend/types/process.ts) 和后端运行结果中，主要状态包括：

- `clarification_required`
- `proposal_ready`
- `ready`
- `failed`

其中最重要的返回体字段为：

- `summary`: 本轮编排结果概述
- `questions`: 追问列表
- `reasoningSummary`: 简洁决策依据
- `warnings`: 警告信息
- `sceneLayout`: 带有最新 `processFlow.connections` 的场景 JSON
- `connectionsPreview`: 面向前端展示的连接摘要

因此，这个 Agent 的规范不是“自由文本回答”，而是“结构化编排结果”。

## 4. 身份定义层如何实现

身份定义层的核心落点在 [backend/agents/composition/agent.py](E:/project/Agentic%20Components/backend/agents/composition/agent.py) 的 `_system_prompt()`。

当前实现把以下约束写入了系统提示：

1. Agent 的身份是工业数字孪生工作区中的工艺流程编排助手
2. 只能使用 `flow_input / flow_output`
3. 只能读取设备 `id / name / type / position`
4. 不能使用 `entry / exit / top / bottom / tool point` 等执行层接口
5. 起始设备或方向不明确时必须返回 `clarification_required`
6. 能生成流程时必须返回 `proposal_ready`
7. 输出必须是 JSON

这意味着“身份定义层”在当前实现里不是单独的配置文件，而是通过系统提示和结果校验共同实现的：

- 系统提示负责约束模型行为边界
- `_sanitize()` 负责过滤不符合约定的模型输出
- `fallback` 机制负责在模型不可用或输出异常时维持稳定行为

## 5. 感知层如何实现

感知层的核心职责是把“原始输入”转换成“可用于编排的内部表示”。

### 5.1 场景感知

场景感知主要在 [backend/agents/composition/parsing.py](E:/project/Agentic%20Components/backend/agents/composition/parsing.py) 中完成：

- `normalize_scene_layout()`
  - 从完整场景 JSON 中抽取设备基础信息
  - 只保留编排需要的字段
  - 同时读出已有 `connections`

经过这一步，Agent 得到的不是复杂场景对象，而是精简后的：

- `devices`
- `connections`

### 5.2 用户意图感知

同一文件中的以下函数负责从自然语言里抽取编排线索：

- `referenced_devices()`: 识别用户提到的设备
- `detect_start_device()`: 推断起始设备
- `detect_end_device()`: 推断终点设备
- `detect_direction()`: 识别“从左到右 / 从右到左 / 从前到后 / 从后到前”
- `conversation_text()`: 将历史消息与当前消息拼接，形成连续上下文

因此当前感知层并不依赖额外外部工具，而是通过“结构化场景 + 规则解析 + 历史消息拼接”完成。

## 6. 规划层如何实现

规划层的核心落点在 [backend/agents/composition/helpers.py](E:/project/Agentic%20Components/backend/agents/composition/helpers.py)。

### 6.1 规划入口

`clarify_or_compose()` 是当前编排 Agent 的主规划函数。

它的执行步骤是：

1. 规范化场景
2. 过滤可参与流程的设备类型
3. 提取现有连接关系
4. 从消息中识别起始设备、终点设备和方向
5. 判断当前信息是否足够
6. 如果不足，生成追问结果
7. 如果足够，排序设备并生成连接

### 6.2 规划策略

当前规划策略是“规则驱动优先，大模型补充其上”：

- 如果场景中没有可编排设备，直接失败
- 如果只有一个可编排设备，直接生成单设备流程
- 如果没有起始设备，先追问
- 如果没有方向，先追问
- 如果信息足够，则按主轴排序生成流程

这里的“主轴”由 `primary_axis()` 判断：

- `x` 方向跨度更大，则按左右关系排序
- `z` 方向跨度更大，则按前后关系排序

### 6.3 重规划能力

当前重规划不是单独的新模块，而是复用同一套编排入口：

- 用户修改时，前端会把当前流程摘要重新带回输入框
- 后端通过 `messages + message + scene_layout.processFlow` 再次运行同一条编排链路
- 现有 `connections` 会作为 `existing` 参与推断

因此当前的“重规划”是基于最新场景状态和最新用户意图的再次求解。

## 7. 工具层如何实现

当前 Agent 的工具层主要由三类能力组成。

### 7.1 场景结构化工具

这部分由本地代码函数承担：

- `normalize_scene_layout()`
- `sceneLayoutConnections()`
- `exportSceneLayout()`

它们本质上是 Agent 的本地工具，负责在前后端之间传递结构化上下文。

### 7.2 LLM 工具

模型调用封装在 [backend/agents/qwen.py](E:/project/Agentic%20Components/backend/agents/qwen.py)。

当前实现方式是：

1. 构造 `system_prompt + user_payload`
2. 通过 DashScope OpenAI Compatible API 请求 Qwen
3. 要求返回 JSON
4. 尝试解析 JSON
5. 如果失败，则回退到本地规则 `fallback`

因此 LLM 在当前系统中的角色不是唯一决策者，而是“在规则结果之上进行补充和润色的高级工具”。

### 7.3 SSE 交互工具

后端流式输出在 [backend/api/agent.py](E:/project/Agentic%20Components/backend/api/agent.py) 中实现。

当前编排 Agent 会输出两类关键事件：

- `clarification_required`
- `process_composition_result`

前端流式读取在 [frontend/components/ai-chat/streamChat.ts](E:/project/Agentic%20Components/frontend/components/ai-chat/streamChat.ts) 中实现，负责把这些结构化事件重新送回聊天面板。

## 8. 行动层如何实现

行动层指 Agent 在完成决策后，如何把结果作用到系统。

### 8.1 后端行动

后端行动主要体现在：

1. 返回结构化结果
2. 输出追问事件
3. 输出流程提案事件
4. 输出最终文本摘要

这些动作由 [backend/agents/pipeline.py](E:/project/Agentic%20Components/backend/agents/pipeline.py) 和 [backend/api/agent.py](E:/project/Agentic%20Components/backend/api/agent.py) 串起来。

### 8.2 前端行动

前端行动主要在 [frontend/components/ai-chat/AIChatPanel.tsx](E:/project/Agentic%20Components/frontend/components/ai-chat/AIChatPanel.tsx) 中完成：

- 收到 `clarification_required` 时，显示 `ProcessClarificationCard`
- 收到 `proposal_ready` 时，显示 `ProcessReviewCard`
- 用户点击 `Apply` 时，把 `sceneLayout.processFlow.connections` 写回场景 store
- 用户点击 `Revise` 时，把当前流程摘要重新带回输入框

真正执行“流程回写”的是：

- `replaceInterfaceConnections()`
- `sceneLayoutConnections()`

这一步非常关键，因为它把 Agent 的输出真正作用到了 Interface 画布状态上。

## 9. 反馈层如何实现

当前反馈层主要由“对话历史 + 当前流程状态 + 用户审批行为”构成。

### 9.1 追问反馈

当用户回答起始设备或方向时：

- 前端把答案重新发给 Agent
- 后端重新进入 `_should_run_composition()`
- Agent 使用新的 `message + messages + scene_layout` 重新编排

### 9.2 提案反馈

当用户看到 proposal 后：

- 可以批准
- 可以取消
- 可以修改

这三种动作都会改变后续上下文：

- 批准会更新画布连接
- 修改会把流程摘要重新送回 Agent
- 新一轮请求会继续带上更新后的 `messages`

### 9.3 模型反馈保护

`QwenAgentClient.complete_json()` 和 `ProcessCompositionAgent._sanitize()` 共同形成了反馈保护：

- 没有可用 API key 时，自动退回本地 `fallback`
- 模型输出不是合法 JSON 时，自动退回 `fallback`
- 模型输出缺少关键字段时，自动退回 `fallback`

因此当前系统的反馈闭环不仅有人机交互反馈，也有模型输出质量反馈。

## 10. 感知 → 决策 → 行动 → 反馈 的完整循环

当前编排 Agent 的完整闭环可以概括为：

```text
用户输入
  ↓
前端导出当前 Scene Layout JSON
  ↓
后端感知层解析 message / messages / scene_layout
  ↓
规划层判断是否信息充足
  ↓
若不足：输出 clarification_required
  ↓
前端展示追问卡片，用户补充答案
  ↓
后端再次感知并重新规划
  ↓
若充足：生成 processFlow.connections
  ↓
输出 proposal_ready
  ↓
前端展示 proposal 审批卡片
  ↓
用户批准或要求修改
  ↓
批准则回写画布连接，修改则重新进入下一轮编排
```

这个循环中：

- 感知负责理解当前场景和用户意图
- 决策负责判断要不要追问、如何排序设备、如何生成连接
- 行动负责把结果以结构化事件和流程连接的形式作用到系统
- 反馈负责把用户补充、用户审批和模型异常重新送回下一轮决策

## 11. 当前实现的关键特点

### 11.1 强约束

当前实现明确区分了：

- 流程层接口：`flow_input / flow_output`
- 执行层接口：`entry / exit / top / bottom / tool point`

编排 Agent 只允许操作前者。

### 11.2 可降级

即使没有大模型 API，当前系统依然可以通过本地规则完成基本编排、追问和提案流程。

### 11.3 可交互

当前实现不是一次性生成 JSON，而是支持：

- 规划前追问
- 规划后审批
- 审批后修改

### 11.4 可继续扩展

后续如果要增强能力，最自然的扩展方向包括：

1. 增加更细的设备角色语义识别
2. 支持“绕过某设备”“优先使用某机器人”等约束
3. 增加更强的多候选流程比较
4. 将确认后的流程结果持久化为正式场景资产
5. 将该 Agent 输出直接作为仿真规划 Agent 的标准输入

## 12. 结论

当前工艺流程编排 Agent 已经不是抽象设计，而是一个真正落地的前后端协同系统：

- 前端负责导出场景、承接追问、展示提案、回写流程
- 后端负责路由分流、规则规划、模型调用、结果校验和流式输出
- 规范层通过 `Scene Layout JSON` 和结构化结果类型约束 Agent 行为边界
- 整体链路已经形成了清晰的 `感知 → 决策 → 行动 → 反馈` 闭环

因此，当前这套实现已经可以作为后续“仿真规划 Agent”的上游标准编排入口。
