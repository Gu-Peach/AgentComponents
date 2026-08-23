# 三 Agent LangGraph 协作架构规划

## 1. 背景

当前 Agent 架构不再采用“场景理解 Agent / 调度规划 Agent / 结果生成 Agent”的三阶段拆法。

新的判断是：AI 的核心目的不是单独解释场景，而是在理解场景的基础上完成仿真调度。因此场景理解应作为调度上下文输入，而不是独立 Agent。LangGraph 中建议保留三个协作 Agent：

- 调度 Agent：根据场景图和用户输入生成仿真调度计划
- 执行 Agent：根据调度计划和设备能力生成轨迹点、运动段和计划时间线
- 结果输出 Agent：基于执行计划实时输出 SimPy 事件、终端日志和前端动画结果

## 2. 场景输入格式

场景理解输入优先采用 behavior 项目中的 `scene_skills/scene.json` 格式，例如：

```text
behavior/frontend/public/demo/Intelligent Storage and Logistics Line/scene_skills/scene.json
behavior/frontend/public/demo/Coordinated Robotic Transfer Unit/scene_skills/scene.json
```

核心结构：

```json
{
  "version": "1.0",
  "name": "智能仓储流水线",
  "description": "物料首先通过传送带传递给升降台...",
  "devices": [
    { "id": "conveyor_1", "configFile": "devices/conveyor_1.json" }
  ],
  "topology": [
    {
      "from": "conveyor_1",
      "to": "smart_storage_1",
      "relation": "feeds",
      "description": "传送带将物料输送至传送带出口"
    }
  ],
  "workflow": [
    "传送带1将物料输送到出口位置"
  ]
}
```

调度 Agent 不需要凭空理解场景，而是读取这个结构化上下文：

- `devices` 给出设备实例和配置文件
- `topology` 给出设备之间的关系
- `workflow` 给出默认工艺步骤
- `devices/*.json` 给出 keyPoints、motion、grid、trajectoryConfig 等执行参数

## 3. 总体架构

```text
用户输入
  +
scene_skills/scene.json
  +
devices/*.json
        |
        v
Scheduling Agent
        |
        v
Execution Agent
        |
        v
Result Output Agent
        |
        v
Terminal Events / SimPy Events / Animation Frames / Assistant Message
```

LangGraph 第一阶段推荐线性编排：

```text
START
  -> scheduling_agent
  -> execution_agent
  -> result_output_agent
  -> validation_node
  -> END
```

后续可以加入条件分支：

```text
validation_node
  -> missing_scene_context: scheduling_agent
  -> invalid_schedule: scheduling_agent
  -> invalid_trajectory: execution_agent
  -> passed: END
```

## 4. 调度 Agent

职责：根据场景图、设备配置和用户输入生成仿真调度计划。

输入：

- 用户自然语言输入
- `scene.json`
- 设备配置文件
- 当前会话历史
- 可用设备动作/skill 列表

处理内容：

- 判断用户想运行哪个工艺流程
- 从 `workflow` 和 `topology` 中推导设备执行顺序
- 选择参与设备
- 规划动作之间的依赖关系
- 规划资源占用关系，例如同一工件、同一夹具、同一仓储格
- 生成调度级别的时序约束

输出示例：

```json
{
  "schedule_plan": {
    "intent": "run_simulation",
    "scene_id": "intelligent_storage_line",
    "actions": [
      {
        "action_id": "a1",
        "device_id": "conveyor_1",
        "action": "transport_to_exit",
        "depends_on": [],
        "start_policy": { "type": "at", "time": 0 }
      },
      {
        "action_id": "a2",
        "device_id": "smart_storage_1",
        "action": "move_to_storage_cell",
        "params": { "targetCellId": "A1", "storageId": "storage" },
        "depends_on": ["a1"],
        "start_policy": {
          "type": "on_event",
          "event": "conveyor_1.exit_reached",
          "offset": 0
        }
      }
    ],
    "temporal_constraints": [
      {
        "from": "a1",
        "to": "a2",
        "relation": "finish_to_start",
        "offset": 0
      }
    ]
  }
}
```

边界：

- 调度 Agent 负责“谁先谁后、谁依赖谁、谁等待哪个事件”
- 调度 Agent 不直接生成轨迹点
- 调度 Agent 不应该直接硬编码所有绝对开始时间
- 用户明确指定时间时，例如“10 秒后启动传送带 2”，调度 Agent 可以写入 `start_policy`

## 5. 执行 Agent

职责：把调度计划转换为可执行运动段，并生成轨迹点。

输入：

- `schedule_plan`
- `scene.json`
- `devices/*.json`
- behavior 中已有轨迹生成能力

复用的 behavior 能力：

- `trajectory-calculator.ts`
- `planConveyorSegment.ts`
- `planRobotArmSegment.ts`
- `planSmartStorageSegment.ts`
- `simulation-plan.ts`
- `simulation-baker.ts`

处理内容：

- 根据设备类型选择轨迹算法
- 为传送带生成线性段
- 为机械臂生成抓取点到放置点的轨迹
- 为智能仓储设备生成格子路径和 `motionData`
- 估算每个动作的持续时间
- 根据调度依赖解析计划时间线

输出示例：

```json
{
  "execution_plan": {
    "segments": [
      {
        "id": "seg_conveyor_1_a1",
        "action_id": "a1",
        "device_id": "conveyor_1",
        "algorithm": "conveyor_linear",
        "planned_start": 0,
        "estimated_duration": 4.2,
        "planned_end": 4.2,
        "waypoints": []
      },
      {
        "id": "seg_smart_storage_1_a2",
        "action_id": "a2",
        "device_id": "smart_storage_1",
        "algorithm": "smart_storage_grid",
        "planned_start": 4.2,
        "estimated_duration": 3.6,
        "planned_end": 7.8,
        "waypoints": [],
        "motionData": {}
      }
    ]
  }
}
```

边界：

- 执行 Agent 负责“怎么动、轨迹点是什么、物理持续时间是多少”
- 执行 Agent 可以把调度约束解析为计划开始/结束时间
- 执行 Agent 不重新解释用户意图
- 执行 Agent 不负责生成最终面向用户的解释

## 6. 结果输出 Agent

职责：基于执行计划实时输出 SimPy 结果、日志和前端可消费事件。

输入：

- `execution_plan`
- 仿真运行状态
- SimPy 事件状态
- Terminal 输出格式
- 前端动画/帧数据格式

处理内容：

- 按 SimPy 仿真时钟推进事件
- 输出 `actual_start`、`actual_end`、等待、阻塞、完成等事件
- 生成 Terminal 日志
- 生成前端动画事件或帧数据
- 汇总仿真结果，例如总时长、吞吐量、瓶颈设备

输出示例：

```json
{
  "type": "simpy_event",
  "time": 4.2,
  "source": "smart_storage_1",
  "event": "started",
  "text": "[  4.20s] smart_storage_1 开始移动到 A1"
}
```

边界：

- 结果输出 Agent 负责“仿真过程中发生了什么”
- 它可以报告实际时间，但不重新规划调度
- 如果运行时发现阻塞或死锁，应把问题反馈给调度 Agent，而不是私自改计划

## 7. 时序关系应该放在哪里

时序关系需要分三层处理，不能全部压给一个 Agent。

### 7.1 调度 Agent：负责逻辑时序

调度 Agent 应负责：

- 动作依赖关系
- 事件触发关系
- 顺序、并行、等待
- 用户显式指定的时间约束
- 资源约束，例如同一工件不能同时被两个设备持有

它输出的是：

```text
A 完成后 B 开始
B 等待 conveyor_1.exit_reached
C 和 D 可以并行
设备 X 需要占用 resource_1
```

这层不适合直接负责所有绝对时间，因为此时还不知道轨迹长度、设备速度、IK 求解结果和真实执行耗时。

### 7.2 执行 Agent：负责物理持续时间和计划时间线

执行 Agent 在生成轨迹点后，才能更准确地得到：

- 轨迹长度
- 设备速度
- 动作持续时间
- `planned_start`
- `planned_end`

因此“下一个设备从哪个时间点开始执行”的计划值，应该由执行 Agent 根据调度 Agent 的依赖图和轨迹持续时间计算出来。

这一步可以看作一个确定性 Time Resolver：

```text
schedule constraints + trajectory durations -> planned timeline
```

它可以先作为 Execution Agent 内部的确定性函数实现，后续再独立成 `time_resolver_node`。

### 7.3 结果输出 Agent：负责仿真实际时间

SimPy 运行后会产生实际时间：

- `actual_start`
- `actual_end`
- `wait_duration`
- `blocked_duration`
- `resource_idle_time`

如果仿真过程中出现资源等待，实际开始时间可能晚于 `planned_start`。因此结果输出 Agent 负责实时报告实际时间，而不是重新决定调度。

推荐结论：

```text
调度 Agent：决定逻辑顺序和触发条件
执行 Agent：生成轨迹并计算计划开始/结束时间
结果输出 Agent：按 SimPy 时钟输出实际运行时间和结果
```

## 8. 共享状态设计

```python
class AgentState(TypedDict):
    session_id: str
    project_id: str
    user_message: str
    messages: list

    scene_skill_path: str
    scene_graph: dict
    device_configs: dict[str, dict]

    schedule_plan: dict | None
    execution_plan: dict | None
    simpy_events: list[dict]
    terminal_events: list[dict]
    final_response: str | None

    validation_errors: list[str]
    pending_questions: list[str]
```

字段归属：

| 字段 | 写入者 | 说明 |
| --- | --- | --- |
| `scene_graph` | Context Loader | 从 `scene.json` 读取 |
| `device_configs` | Context Loader | 从 `devices/*.json` 读取 |
| `schedule_plan` | Scheduling Agent | 调度计划和逻辑时序 |
| `execution_plan` | Execution Agent | 轨迹点、运动段、计划时间线 |
| `simpy_events` | Result Output Agent | SimPy 实时事件 |
| `terminal_events` | Result Output Agent | 终端输出 |
| `validation_errors` | Validation Node | schema 与一致性错误 |

## 9. 第一阶段落地范围

第一阶段建议做最小可跑闭环：

- 读取一个 demo 的 `scene_skills/scene.json`
- 读取对应 `devices/*.json`
- 调度 Agent 根据用户输入生成 `schedule_plan`
- 执行 Agent 复用 behavior 的轨迹生成逻辑生成 `execution_plan`
- Execution Agent 内部先实现简单 Time Resolver
- 结果输出 Agent 先生成 mock SimPy event stream
- 前端聊天区接收 SSE，并把日志写入 Terminal

第一阶段暂不做：

- 完整资源冲突求解
- 随机事件
- 复杂死锁恢复
- 多方案优化
- 真实长期运行的 SimPy worker

## 10. 关键设计原则

- 场景理解是输入上下文，不单独做 Agent
- 调度 Agent 不生成轨迹点
- 执行 Agent 不重做用户意图理解
- 结果输出 Agent 不私自修改计划
- 计划时间和实际时间必须区分
- behavior 的轨迹生成能力应通过清晰 adapter 复用，避免把旧前端工具直接耦合进后端
