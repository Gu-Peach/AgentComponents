# 当前双 Agent 仿真实现说明

## 1. 当前定位

当前项目中正在形成的是一个面向仿真运行的双 Agent 架构：

```text
用户输入 + 当前场景
        |
        v
流程规划 Agent
        |
        v
执行 Agent
        |
        v
前端确认 / 动画执行 / SimPy 日志 / Observation
```

这里的“两 Agent”不是旧文档中的“场景理解、调度、结果输出”三段拆法，而是更贴近当前实现的两个职责层：

- 流程规划 Agent：根据当前场景设备和用户目标，规划或修订工艺流程连接。
- 执行 Agent：根据已存在的流程、`scene_skills` 或调度计划，生成可播放的动作段、轨迹点、时间线和运行事件。

后端入口统一在 `backend/api/agent.py`，核心编排在 `backend/agents/pipeline.py`。前端入口统一在 `frontend/components/ai-chat/AIChatPanel.tsx`。

## 2. 两类场景输入

当前系统实际支持两类输入，它们服务于不同阶段。

### 2.1 Scene Layout JSON

Scene Layout JSON 由前端当前工作区导出，代码位置是 `frontend/lib/process/sceneLayout.ts`。

它描述当前用户摆放的设备、设备位姿、流程连接和仿真策略：

```json
{
  "schemaVersion": "scene-layout/v1",
  "layout": {
    "devices": []
  },
  "processFlow": {
    "connections": []
  },
  "simulation": {
    "workpieceDeviceId": "object",
    "executionPolicy": {
      "conveyorAlwaysRunsEntryToExit": true,
      "robotPlaceHeight": 1,
      "robotUsesRuntimeEndEffectorStart": true
    }
  }
}
```

它主要提供给流程规划 Agent 使用。流程规划 Agent 只关心流程层输入输出口：

- `flow_input`
- `flow_output`

它不直接使用执行层接口，例如 `entry`、`exit`、`top`、`bottom`、`tool point`。

### 2.2 scene_skills

`scene_skills` 来自 demo 目录，例如：

```text
frontend/public/demo/Intelligent Storage and Logistics Line/scene_skills/scene.json
frontend/public/demo/Intelligent Storage and Logistics Line/scene_skills/devices/*.json
```

它主要提供给执行 Agent 链路使用，包含：

- `scene.json`：设备列表、拓扑关系、默认 workflow。
- `devices/*.json`：设备类型、关键点、运动参数、仓位网格、节点名。

执行 Agent 依赖这些配置生成真实可播放的 `execution_plan`。

## 3. 后端统一入口

请求模型在 `backend/schemas/agent.py` 中定义：

```python
class AgentRunRequest(BaseModel):
    message: str
    scene_name: str
    scene_skill_path: str | None
    session_id: str
    scene_layout: dict[str, Any] | None
    messages: list[dict[str, Any]]
```

前端通过 `frontend/components/ai-chat/streamChat.ts` 调用：

```text
POST /api/agent/stream
```

Next.js 代理路由位于：

```text
frontend/app/api/agent/stream/route.ts
```

后端 FastAPI 路由位于：

```text
backend/api/agent.py
```

主要接口：

- `POST /api/agent/run`：一次性返回结构化结果。
- `POST /api/agent/stream`：通过 SSE 返回 Agent 事件。
- `POST /api/agent/step/start`：创建 step session。
- `GET /api/agent/step/{session_id}`：查询当前 step。
- `POST /api/agent/step/observe`：提交前端 observation。

## 4. Agent 路由逻辑

`backend/agents/pipeline.py` 中的 `AgentPipeline.run()` 会先判断是否进入流程规划分支。

判断函数是 `_should_run_composition()`，触发条件包括：

- 用户输入包含“编排”“工艺流程”“流程”“自动连接”等关键词。
- 英文输入包含 `process flow`、`compose process`。
- 最近对话中存在 process proposal 上下文，并且用户继续回答起点、方向或修改请求。

如果满足条件：

```text
AgentPipeline -> ProcessCompositionAgent
```

否则进入仿真执行链路：

```text
AgentPipeline
  -> detect_missing_requirements
  -> SchedulingAgent
  -> build_action_specs
  -> build_world_state
  -> validate_closed_loop
  -> ExecutionAgent
  -> build_observations
  -> ResultOutputAgent
```

从当前使用体验看，可以把 `SchedulingAgent + ExecutionAgent + ResultOutputAgent` 视为“执行 Agent 链路”的内部实现。后续如果要更严格地保持双 Agent 架构，可以把这些内部节点收敛到 `SimulationExecutionAgent` 门面类下。

## 5. 流程规划 Agent

代码位置：

```text
backend/agents/composition/agent.py
backend/agents/composition/helpers.py
backend/agents/composition/parsing.py
```

### 5.1 目标

流程规划 Agent 的目标是把当前工作区设备编排成工艺流程连接。它不负责动画，也不负责轨迹生成。

输入：

- 用户当前消息。
- 最近对话历史。
- `Scene Layout JSON`。
- 当前已有 `processFlow.connections`。

输出：

- `clarification_required`：缺少起点或方向，需要问用户。
- `proposal_ready`：生成流程连接提案，等待用户确认。
- `ready`：可直接应用的流程。
- `failed`：无法编排。

### 5.2 确定性 fallback

`ProcessCompositionAgent.run()` 先调用 `clarify_or_compose()` 生成 fallback，再调用 Qwen：

```text
clarify_or_compose -> Qwen complete_json -> sanitize
```

这样做的意义是：即使大模型失败，系统仍能用规则生成可解释结果。

当前规则包括：

- 过滤可参与流程的设备类型：`conveyor`、`robot`、`lift`、`storage`。
- 如果起点不明确，返回起点追问。
- 如果流转方向不明确，返回方向追问。
- 如果信息足够，按设备空间位置排序并生成连接。

生成的连接统一使用：

```json
{
  "sourceDeviceId": "conveyor_1",
  "sourceInterface": "flow_output",
  "targetDeviceId": "robot_1",
  "targetInterface": "flow_input"
}
```

### 5.3 前端交互

前端在 `AIChatPanel.tsx` 中处理流程规划结果：

- `clarification_required`：显示 `ProcessClarificationCard`。
- `proposal_ready`：显示 `ProcessReviewCard`。
- 用户点击确认后，调用 `replaceInterfaceConnections()` 写回 `sceneStore`。
- 用户点击修改后，把当前流程摘要填回输入框，触发下一轮修订。

这已经形成了一个人机协商式流程规划闭环。

## 6. 执行 Agent

当前执行 Agent 是一条复合链路，主要由以下模块组成：

```text
backend/agents/scheduling.py
backend/agents/closed_loop/clarifier.py
backend/agents/closed_loop/actions.py
backend/agents/closed_loop/state.py
backend/agents/closed_loop/validator.py
backend/agents/execution.py
backend/agents/results.py
backend/agents/closed_loop/runtime.py
```

### 6.1 缺失条件追问

在执行链路进入调度前，会先运行：

```text
detect_missing_requirements(state)
```

当前已经支持的规则包括：

- 用户说“把物料放到仓位”但没有指定 A1/A2 等仓位时，返回 `clarification_required`。
- 用户要求修改计划但缺少修改范围或倍率时，返回追问。
- 多机械臂场景中用户指定“用机械臂”但没有指明设备时，返回追问。

这个节点的作用是阻止调度器偷偷使用默认值，例如默认把 `targetCellId` 填成 A1。

### 6.2 调度计划生成

`SchedulingAgent` 根据 `scene.json.topology` 生成动作序列：

```json
{
  "action_id": "a1",
  "device_id": "conveyor_1",
  "action": "transport_to_exit",
  "depends_on": [],
  "params": {},
  "start_policy": { "type": "at", "time": 0 },
  "source": "conveyor_1",
  "target": "smart_storage_1"
}
```

它负责：

- 选择动作设备。
- 判断动作名称。
- 建立 `depends_on`。
- 生成 `temporal_constraints`。
- 将 LLM 输出约束回 fallback 结构，避免设备顺序被模型乱改。

虽然它现在仍叫 `SchedulingAgent`，但在双 Agent 视角中，它属于执行 Agent 内部的“调度子节点”。

### 6.3 计划校验

调度计划会被转换成 `action_specs`，并进入 validator：

```text
build_action_specs(schedule_plan)
build_world_state(device_configs, action_specs)
validate_closed_loop(...)
```

当前 validator 的职责是把执行前的明显错误挡住，例如设备、仓位、依赖和执行计划结构问题。

### 6.4 轨迹与时间线生成

`ExecutionAgent` 把 `schedule_plan.actions` 转成 `execution_plan.segments`。

不同设备类型对应不同算法：

| 设备类型 | algorithm | 轨迹来源 |
| --- | --- | --- |
| `conveyor` | `conveyor_linear` | `conveyor_waypoints()` |
| `robot_arm` | `robot_arm_ik` | `robot_pick()`、`robot_place()`、`robot_waypoints()` |
| `smart_storage` | `smart_storage_grid` | `smart_storage_waypoints()` 或 `smart_storage_waypoints_between()` |

每个 segment 包含：

```json
{
  "id": "seg_conveyor_1_a1",
  "action_id": "a1",
  "device_id": "conveyor_1",
  "device_type": "conveyor",
  "algorithm": "conveyor_linear",
  "waypoints": [],
  "estimated_duration": 2.8,
  "planned_start": 0,
  "planned_end": 2.8
}
```

`planned_start` 由依赖动作的 `planned_end` 解析出来；没有依赖时读取 `start_policy.time`。

### 6.5 结果输出

`ResultOutputAgent` 基于 execution plan 生成结果事件：

- `simpy_event`
- `summary`
- `agent_status`

SSE 输出顺序在 `backend/api/agent.py` 中定义：

```text
schedule_plan
action_specs
world_state
validation_result
execution_plan
step_session
observations
simpy_event / summary / agent_status
final_response
DONE
```

前端不会立即播放，而是把 `execution_plan` 暂存在 `PlanReviewCard` 中，等待用户点击 Run。

## 7. 前端执行闭环

主要代码位置：

```text
frontend/components/ai-chat/AIChatPanel.tsx
frontend/components/ai-chat/PlanReviewCard.tsx
frontend/stores/simulationStore.ts
frontend/components/simulation/SimulationClock.tsx
frontend/components/viewport/simulation/AgentSimulationAnimator.tsx
frontend/components/viewport/simulation/animationRuntime.ts
```

当前行为：

1. 用户输入仿真请求。
2. 前端发送 `message`、`messages`、`sceneName`、`sceneLayout`。
3. 后端返回 `execution_plan` 和 `step_session`。
4. 前端显示计划确认卡片。
5. 用户点击 Run 后写入 `simulationStore.executionPlan`。
6. R3F 动画执行器读取 segment 并播放。
7. `SimulationClock` 按动画时间输出日志，并向后端提交 observation。

这已经实现了“执行前人工确认 + 执行后 observation 回传”的基础闭环。

## 8. 共享状态字段

后端共享状态定义在 `backend/agents/models.py`：

```python
@dataclass
class AgentState:
    session_id: str
    project_id: str
    user_message: str
    messages: list[dict[str, Any]]
    scene_skill_path: str
    scene_graph: dict[str, Any]
    device_configs: dict[str, dict[str, Any]]
    scene_layout: dict[str, Any] | None
    schedule_plan: dict[str, Any] | None
    composition_result: dict[str, Any]
    action_specs: list[dict[str, Any]]
    world_state: dict[str, Any]
    validation_result: dict[str, Any]
    clarification_result: dict[str, Any]
    execution_plan: dict[str, Any] | None
    observations: list[dict[str, Any]]
    result_events: list[dict[str, Any]]
    final_response: str | None
```

可以看出，当前状态同时承载了流程规划和仿真执行两条链路。

## 9. 当前已经实现的能力

- 基于 Scene Layout JSON 的工艺流程编排。
- 流程规划前追问起点和方向。
- 流程提案审阅、确认和修订。
- 基于 scene_skills 的仿真动作调度。
- 仿真规划前追问缺失仓位、设备或修订参数。
- 调度计划转 `ActionSpec`。
- 世界状态构建与计划校验。
- 设备类型对应的确定性轨迹生成。
- 执行计划用户确认后再播放。
- SimPy/Terminal 事件跟随动画时间输出。
- 前端 observation 回传与 step runtime 基础协议。

## 10. 当前边界和问题

### 10.1 命名与结构仍在过渡

当前 `SchedulingAgent`、`ExecutionAgent`、`ResultOutputAgent` 仍保留三段命名。但从产品理解上，它们更像执行 Agent 内部的三个子节点。

建议后续引入一个门面：

```text
SimulationExecutionAgent
  -> requirement_resolver
  -> scheduler
  -> validator
  -> motion_planner
  -> result_streamer
```

### 10.2 Pipeline 职责偏重

`AgentPipeline` 现在同时负责：

- 判断是否走流程规划。
- 创建流程规划状态。
- 创建仿真执行状态。
- 串接调度、校验、执行、结果。
- 组织返回数据。

这是一个轻微的 Rigidity/Obscurity 风险。建议后续拆成：

```text
ProcessCompositionPipeline
SimulationExecutionPipeline
AgentRouteDispatcher
```

当前阶段先文档化，不立即重构。

### 10.3 设备仿真规范仍未完全契约化

目前缺参追问主要靠规则判断，例如仓位、机械臂选择、修订参数。后续更好的方式是给每类设备增加 `simulationRequirements`，让 Agent 按设备契约检查：

```json
{
  "simulationRequirements": {
    "planning": {
      "required": ["targetCellId"],
      "askPolicy": "ask_if_missing"
    },
    "execution": {
      "required": ["rootNodeName", "carrierNodeName", "motion.rootAxis"],
      "askPolicy": "auto_detect_then_ask"
    }
  }
}
```

这样流程规划和执行规划都能从“规则散落”升级为“设备契约驱动”。

## 11. 推荐下一步

建议下一步不要继续扩大 prompt，而是补三个结构层：

1. 增加设备级 `simulationRequirements`。
2. 新增 `RequirementResolver`，统一处理规划阶段和执行阶段缺失条件。
3. 将现有执行链路收敛为 `SimulationExecutionAgent`，让外部文档和代码命名一致。

完成后，当前架构可以稳定表述为：

```text
ProcessPlanningAgent
  负责工艺流程如何连接

SimulationExecutionAgent
  负责流程/场景如何变成可执行动画与仿真事件
```
