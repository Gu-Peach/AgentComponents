# 工艺流程编排 Agent 技术方案

## 1. 总体定位

工艺流程编排 Agent 是场景搭建完成后的第一个智能 agent。它不负责执行仿真，也不负责生成机械臂轨迹，而是负责把场景中的设备组织成一份可理解、可验证、可复用的工艺流程 JSON。

系统最终保留两个核心 Agent：

1. `工艺流程编排 Agent`
   输入当前场景设备信息，输出 `Scene Layout JSON` 中的 `processFlow`。

2. `仿真规划 Agent`
   输入用户仿真需求和已编排好的 `Scene Layout JSON`，输出可执行仿真方案。

编排 Agent 的核心循环是：

```text
感知 -> Schema 校验 -> 规划 -> 工具调用 -> 行动 -> 反馈记忆
```

## 2. Profile 身份定义层

### 2.1 角色设定

你是工业数字孪生平台中的工艺流程编排助手。

你的职责是根据当前场景中的设备信息，生成标准的 `Scene Layout JSON`，重点完成 `processFlow.connections` 的编排。

### 2.2 能力边界

可以做：

- 读取场景中的设备基础信息。
- 判断设备在工艺流程中的上下游关系。
- 使用流程层输入输出口生成连接。
- 生成 `Scene Layout JSON`。
- 在信息不足或存在多种合理路径时向用户追问。

不能做：

- 读取或推理执行层接口，如 `entry / exit / top / bottom / tool point`。
- 生成机械臂 IK 轨迹。
- 生成仿真执行段。
- 直接驱动仿真运行时。
- 擅自决定有明显歧义的工艺目标。

### 2.3 默认行为准则

- 场景关系明确时，直接生成流程编排。
- 存在多个合理流程候选时，触发澄清问答。
- 缺少可执行流程所需的关键设备时，返回不可编排原因。
- 可选信息缺失时，使用系统默认值并写入 `warnings`。

### 2.4 输出风格

Agent 输出必须是结构化 JSON，不输出自由文本作为最终结果。

可附带简短的 `reasoningSummary` 和 `warnings`，但真实可执行结果必须落在 `sceneLayout.processFlow` 中。

## 3. Perception 感知层

### 3.1 输入来源

编排 Agent 接收三类输入：

- 用户自然语言指令
- 当前场景设备列表
- 系统提供的流程层设备语义

当前阶段场景设备信息只需要：

- 设备 `id`
- 设备名称 `name`
- 设备类型 `type`
- 设备位置 `position`

不需要提供：

- `modelUrl`
- `interfaceUrl`
- `rotation`
- `scale`
- 执行层接口配置

### 3.2 输入规范化

感知层需要把用户输入转为内部意图表示：

```json
{
  "intent": "compose_process_flow",
  "targetMode": "auto",
  "constraints": {
    "startDeviceId": null,
    "endDeviceId": null,
    "preferredRobotId": null
  }
}
```

示例：

- “帮我自动编排这个场景” -> `targetMode = auto`
- “从左侧传送带到右侧传送带” -> 提取起点和终点方向约束
- “用 robot_1 搬运” -> 提取首选机器人约束

### 3.3 场景规范化

工具返回的设备信息应规范化为：

```json
{
  "devices": [
    {
      "id": "conveyor_1",
      "name": "Conveyor 1",
      "type": "conveyor",
      "position": { "x": 0, "y": 0, "z": 0 }
    }
  ]
}
```

## 4. Schema / Ontology 领域规范层

### 4.1 业务实体

编排 Agent 只理解流程层实体：

- `ProcessDevice`
- `ProcessPort`
- `ProcessConnection`
- `ProcessFlow`
- `ClarificationQuestion`

### 4.2 设备流程角色

建议定义如下角色：

```json
{
  "conveyor": {
    "role": "transport",
    "ports": ["flow_input", "flow_output"],
    "canBeSource": true,
    "canBeTarget": true
  },
  "robot": {
    "role": "transfer",
    "ports": ["flow_input", "flow_output"],
    "canBeSource": true,
    "canBeTarget": true
  },
  "workpiece": {
    "role": "passive_workpiece",
    "ports": [],
    "canBeSource": false,
    "canBeTarget": false
  }
}
```

### 4.3 字段校验规则

`ProcessConnection` 必须满足：

- `sourceDeviceId` 必填，且设备存在。
- `targetDeviceId` 必填，且设备存在。
- `sourceInterface` 必须是 `flow_output`。
- `targetInterface` 必须是 `flow_input`。
- `sourceDeviceId` 不能等于 `targetDeviceId`。
- `workpiece` 不能作为主动连接节点。

### 4.4 追问策略

必须追问：

- 多个起点候选无法判断。
- 多个终点候选无法判断。
- 多个机器人都可承担同一段转运。
- 用户明确目标和空间推断结果冲突。

可以默认：

- 未指定物料时，选择场景中的第一个 `workpiece` 作为被执行对象。
- 未指定流程方向时，按设备空间分布推断主方向。

## 5. Memory 记忆层

### 5.1 In-context Memory

保存当前对话中的用户意图、澄清回答和本轮生成的流程候选。

用途：

- 用户补充“用第二个传送带作为起点”后继续同一轮编排。
- 用户要求“换一个机器人”后更新候选流程。
- 用户基于已生成流程提出“把终点换成 conveyor_3”后触发重规划。
- 用户确认某个候选流程后，将其标记为本轮有效方案。

### 5.2 External Memory

保存长期项目偏好和历史场景编排结果。

示例：

- 用户偏好从左到右作为默认物流方向。
- 某类场景中机器人通常作为两个传送带之间的转运设备。
- 历史成功编排的 `Scene Layout JSON`。

### 5.3 Episodic Memory

保存一次完整编排会话摘要。

示例：

```text
用户在 2026-05-09 的场景中确认 conveyor_1 为起点，robot_1 为转运设备，conveyor_2 为终点。
```

### 5.4 Procedural Memory

保存固化流程和示例。

示例：

- 单传送带场景：`conveyor`
- 传送带-机器人-传送带：`conveyor -> robot -> conveyor`
- 多机器人歧义场景：触发澄清

## 6. Planning 规划层

### 6.1 任务分解

规划层按以下步骤执行：

1. 读取场景设备。
2. 过滤掉 `workpiece` 主动连接节点。
3. 识别可参与流程的设备。
4. 判断是否需要规划前澄清。
5. 基于用户补充信息推断候选起点、转运设备、终点和流转方向。
6. 生成一个或多个流程候选。
7. 调用校验工具。
8. 输出流程提案、澄清问题或失败原因。

### 6.2 规划策略

默认使用空间关系和设备角色共同推断：

- conveyor 常作为源设备或目标设备。
- robot 常作为中间转运设备。
- workpiece 只作为被执行对象。
- 线性布局优先生成线性流程。

### 6.3 不确定性处理

如果存在多个等价候选，不继续猜测。

输出：

```json
{
  "status": "clarification_required",
  "questions": [
    {
      "id": "preferred_robot",
      "question": "检测到 robot_1 和 robot_2 都可以作为转运设备，请选择一个。"
    }
  ]
}
```

### 6.4 重规划机制

当用户反馈“不对，应该先经过 conveyor_2”时：

1. 保留原场景设备信息。
2. 将用户反馈写入当前上下文。
3. 重新生成候选流程。
4. 再次校验。
5. 输出新的 `Scene Layout JSON`。

## 7. User Interaction 用户交互闭环

编排 Agent 与用户的交互分为两个阶段：

1. 规划前信息获取
2. 规划后结果修改

这两个阶段都属于 Human-in-the-loop，但触发时机和目标不同。

### 7.1 规划前信息获取

当 Agent 读取场景设备后，如果发现流程存在多个合理解释，应先向用户获取关键信息。

典型问题包括：

- 从哪个设备开始流转？
- 物料最终流向哪个设备？
- 物料流转方向是从左到右、从右到左，还是按用户指定顺序？
- 多个机器人存在时，优先使用哪个机器人？
- 是否需要经过全部设备，还是只连接其中一部分？

规划前问题应尽量短，并提供可选项。

示例：

```json
{
  "type": "process_composition_result",
  "status": "clarification_required",
  "stage": "pre_planning",
  "questions": [
    {
      "id": "start_device",
      "question": "请确认物料从哪个设备开始流转。",
      "options": [
        { "label": "Conveyor 1", "value": "conveyor_1" },
        { "label": "Conveyor 2", "value": "conveyor_2" }
      ]
    },
    {
      "id": "flow_direction",
      "question": "请确认物料流转方向。",
      "options": [
        { "label": "从左到右", "value": "left_to_right" },
        { "label": "从右到左", "value": "right_to_left" }
      ]
    }
  ]
}
```

用户回答后，Agent 将答案写入当前上下文，并继续规划。

### 7.2 规划结果提案

当 Agent 生成流程后，不应立即把结果视为最终事实，而应形成可确认的流程提案。

提案应包含：

- 生成的 `Scene Layout JSON`
- 简短流程摘要
- 可读的连接列表
- warnings
- 可继续修改的提示状态

示例：

```json
{
  "type": "process_composition_result",
  "status": "proposal_ready",
  "stage": "post_planning",
  "summary": "已生成 conveyor_1 -> robot_1 -> conveyor_2 的工艺流程。",
  "connectionsPreview": [
    "conveyor_1.flow_output -> robot_1.flow_input",
    "robot_1.flow_output -> conveyor_2.flow_input"
  ],
  "sceneLayout": {
    "schemaVersion": "scene-layout/v1",
    "layout": {},
    "processFlow": {},
    "simulation": {}
  },
  "warnings": []
}
```

### 7.3 规划后结果修改

用户可以基于提案继续修改。

常见修改包括：

- 更换起点设备
- 更换终点设备
- 更换中间机器人
- 插入一个中间设备
- 删除某段连接
- 反转流程方向
- 指定某些设备不参与流程

示例用户反馈：

```text
不要用 robot_1，用 robot_2。
```

Agent 应转换为修订约束：

```json
{
  "revisionIntent": "replace_transfer_device",
  "constraints": {
    "oldDeviceId": "robot_1",
    "newDeviceId": "robot_2"
  }
}
```

然后重新执行：

```text
读取当前提案 -> 应用修订约束 -> 重新生成 processFlow -> 校验 -> 输出新提案
```

### 7.4 确认与提交

当用户确认提案后，Agent 输出最终结果：

```json
{
  "type": "process_composition_result",
  "status": "ready",
  "stage": "confirmed",
  "sceneLayout": {
    "schemaVersion": "scene-layout/v1",
    "layout": {},
    "processFlow": {},
    "simulation": {}
  }
}
```

系统随后可以：

- 更新 Interface 画布连接
- 写入 `Scene Layout JSON`
- 将结果交给仿真规划 Agent
- 将用户确认结果写入记忆

### 7.5 交互状态机

建议使用以下状态：

```text
idle
  -> collecting_context
  -> clarification_required
  -> planning
  -> proposal_ready
  -> revising
  -> ready
  -> failed
```

状态说明：

- `clarification_required`：规划前缺少关键信息。
- `proposal_ready`：流程已生成，但等待用户确认或修改。
- `revising`：用户基于提案提出修改，Agent 正在重规划。
- `ready`：用户确认，流程成为正式输出。

## 8. Tool Use 工具层

### 8.1 `getSceneDevices()`

返回当前场景设备基础信息。

返回示例：

```json
{
  "devices": [
    {
      "id": "conveyor_1",
      "name": "Conveyor 1",
      "type": "conveyor",
      "position": { "x": 0, "y": 0, "z": 0 }
    }
  ]
}
```

### 8.2 `getProcessPorts(deviceId)`

返回流程层输入输出口，不返回执行层接口。

返回示例：

```json
{
  "deviceId": "robot_1",
  "ports": ["flow_input", "flow_output"]
}
```

### 8.3 `getDeviceProcessRole(deviceId)`

返回设备流程角色。

返回示例：

```json
{
  "deviceId": "robot_1",
  "role": "transfer",
  "canBeSource": true,
  "canBeTarget": true
}
```

### 8.4 `validateProcessFlow(connections)`

校验编排结果是否合法。

返回示例：

```json
{
  "valid": true,
  "errors": [],
  "warnings": []
}
```

### 8.5 `exportSceneLayoutWithProcessFlow(connections)`

把编排结果写入标准 `Scene Layout JSON`。

这个工具负责拼装最终输出，但不负责编译执行层轨迹。

### 8.6 工具失败策略

- 场景读取失败：返回 `failed`，提示无法获取场景。
- 流程校验失败：返回 `clarification_required` 或 `failed`。
- JSON 输出失败：返回 `failed`，附带错误字段。

## 9. Action 行动层

### 9.1 输出 ready 结果

当流程明确且校验通过时，输出：

```json
{
  "type": "process_composition_result",
  "status": "ready",
  "sceneLayout": {
    "schemaVersion": "scene-layout/v1",
    "layout": {},
    "processFlow": {
      "connections": []
    },
    "simulation": {}
  },
  "reasoningSummary": [],
  "warnings": []
}
```

### 9.2 输出澄清问题

当信息不足时，输出：

```json
{
  "type": "process_composition_result",
  "status": "clarification_required",
  "questions": []
}
```

### 9.3 输出流程提案

当流程已生成但还未确认时，输出 `proposal_ready`。

此时系统可以在 Interface 画布中预览连接，但不一定立即覆盖用户已有连接。

### 9.4 更新系统状态

Agent 输出 ready 后，系统可以：

- 更新 `sceneStore.interfaceConnections`
- 生成 `Scene Layout JSON`
- 将该 JSON 交给仿真规划 Agent
- 写入用户确认记录

### 9.5 Human-in-the-loop

需要人工确认时，系统暂停编排流程，等待用户回答后继续规划。

## 10. 完整运行流程

```text
用户输入
  -> Perception: 意图识别与场景规范化
  -> Schema: 流程实体与字段校验
  -> Planning: 判断是否需要规划前澄清
  -> User Interaction: 收集起点、方向、优先设备等信息
  -> Planning: 生成候选流程或修订流程
  -> Tool Use: 校验流程并导出 JSON
  -> Action: 输出 clarification_required / proposal_ready / ready / failed
  -> Memory: 写入用户反馈和成功编排结果
```

## 11. 与仿真规划 Agent 的关系

编排 Agent 输出的是流程结构，不是仿真计划。

仿真规划 Agent 后续读取：

- `layout`
- `processFlow`
- `simulation`

然后再结合用户仿真需求生成执行计划。

因此，两者之间的边界是：

- 编排 Agent：决定设备之间怎么连。
- 仿真规划 Agent：决定这条流程如何执行。

## 12. 当前落地重点

后续实现应优先完成：

- 编排 Agent profile
- 场景设备读取工具
- 流程口工具
- 设备流程角色工具
- 流程校验工具
- 标准 JSON 输出工具
- 澄清问答循环
- 提案预览与修改循环
- 用户确认后的状态提交

完成后，编排 Agent 就具备完整闭环：

```text
读取场景 -> 规划前询问 -> 生成提案 -> 用户修改或确认 -> 校验流程 -> 输出 JSON -> 写入反馈 -> 重规划
```
