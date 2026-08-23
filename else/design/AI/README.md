# AI Agent 仿真架构设计

> LangGraph + SimPy
> 调度与执行分离 · 场景驱动

---

## 📋 核心架构思想

### 调度与执行分离

```
用户输入（自然语言 / 文档）
    │
    ▼
┌─────────────────────────────────────────────────┐
│           AI 调度层（LangGraph Agent）            │
│                                                   │
│  理解意图 → 解析场景 → 生成仿真计划（SimPlan）    │
│  ↓                                               │
│  确定：每个设备的仿真参数、执行时序、协调逻辑     │
└─────────────────────┬───────────────────────────┘
                      │ SimPlan JSON
                      ▼
┌─────────────────────────────────────────────────┐
│           执行层（SimPy + 轨迹算法）              │
│                                                   │
│  SimPy 事件驱动引擎                              │
│  ├── ConveyorProcess   → continuous_transport    │
│  ├── LiftProcess       → lift_xy_trajectory      │
│  └── StorageProcess    → cell_allocation_fifo    │
│                                                   │
│  输出：帧数据 → WebSocket → 前端动画             │
│  输出：日志流 → Terminal Panel                   │
└─────────────────────────────────────────────────┘
```

**关键边界**：
- **Agent 职责**：读文件、理解场景、决定"什么时候用什么参数做什么"
- **轨迹算法职责**：给定参数，计算具体运动序列
- **SimPy 职责**：按时序调度各设备进程，驱动事件

---

## 🔧 LangGraph Agent 架构

### 完整节点图

```
用户输入
    │
    ▼
[Intent Parser]          解析用户意图，判断输入复杂度
    │
    ├─ simple ──→ [Scene Reader]      读 scene.json + 设备配置
    │
    └─ detailed ─→ [Doc Parser]       解析用户上传的仿真文档
                       │
                       ▼
               [Scene Reader]         读 scene.json + 设备配置
                   │
                   ▼
           [Topology Analyzer]        分析设备拓扑，确定执行顺序
                   │
                   ▼
           [Param Resolver]           为每个设备确定仿真参数
                   │
                   ├── 参数完整 ──→  [Plan Generator]
                   │
                   └── 参数缺失 ──→  [Clarifier] ──→ 向用户追问
                                                           │
                                                     [Param Resolver]
                   ▼
           [Plan Generator]           生成结构化 SimPlan JSON
                   │
                   ▼
           [Plan Validator]           校验计划可行性（死锁/冲突检测）
                   │
                   ├── 通过 ──→  [SimPy Executor]    提交 Celery 执行
                   │
                   └── 失败 ──→  [Plan Fixer] ──→ 修正后重新校验
                   ▼
           [SimPy Executor]
                   │
                   ├── 仿真日志 ──→  WebSocket ──→ Terminal Panel
                   └── 帧数据   ──→  WebSocket ──→ 3D 动画
```

### Agent 状态定义

```python
class SimAgentState(TypedDict):
    # 输入
    session_id: str
    project_id: str
    user_message: str
    uploaded_docs: list[str]
    
    # 解析结果
    messages: Annotated[list, add_messages]
    intent: Optional[dict]
    input_complexity: Literal["simple", "medium", "detailed"]
    
    # 场景信息
    scene_doc: Optional[dict]
    device_configs: dict[str, dict]
    topology_order: list[str]
    
    # 仿真计划
    sim_plan: Optional[dict]
    validation_errors: list[str]
    retry_count: int
    
    # Human-in-loop
    pending_questions: list[str]
    clarification_answers: dict
    
    # 输出
    task_id: Optional[str]
    final_response: str
```

---

## 📄 SimPlan 结构

Agent 输出，SimPy 输入的契约格式：

```json
{
  "plan_version": "1.0",
  "scene_id": "project_uuid",
  "sim_config": {
    "duration": 3600,
    "warm_up": 0,
    "random_seed": 42,
    "speed_multiplier": 1.0
  },
  "device_plans": [
    {
      "device_id": "conveyor_1",
      "device_type": "conveyor",
      "algorithm": "continuous_transport",
      "params": {
        "speed": 300,
        "length": 2000,
        "part_interval": 8.0
      },
      "triggers": {
        "start": "sim_start"
      },
      "continuous": true
    },
    {
      "device_id": "smart_storage_1",
      "device_type": "lift",
      "algorithm": "lift_xy_trajectory",
      "params": {
        "root_axis": "x",
        "carrier_axis": "y",
        "root_range": { "min": -4.142, "max": 0.858 },
        "carrier_range": { "min": 0.185, "max": 3.160 },
        "speed": 0.5,
        "home_position": { "root": 0.858, "carrier": 0.185 },
        "key_points": [
          { "name": "transfer_board", "nodeName": "Z_00En" }
        ]
      },
      "triggers": {
        "start": "conveyor_1.part_at_exit"
      },
      "continuous": false
    }
  ],
  "coordination_rules": [
    {
      "type": "signal",
      "when": "conveyor_1.part_at_exit",
      "trigger": "smart_storage_1.fetch_part",
      "description": "传送带出口有物料时，触发升降台取料"
    },
    {
      "type": "resource_wait",
      "resource": "storage.cells",
      "condition": "has_empty",
      "blocked_device": "smart_storage_1",
      "description": "仓储柜满时升降台等待"
    }
  ],
  "plan_summary": "智能仓储流水线仿真，传送带 300mm/s，升降台 0.5m/s"
}
```

---

## 🛠️ Skills 系统

每个 Skill 是可复用的工具函数，Agent 通过 ToolNode 调用：

### 1. read_scene_config

读取场景配置文件和所有设备配置：

```python
@tool
async def read_scene_config(project_id: str) -> dict:
    """读取完整场景描述，包括设备列表、拓扑关系、工作流"""
    scene = await mongo.scenes.find_one({"_id": project_id})
    device_configs = {}
    for device in scene["devices"]:
        device_configs[device["layout_device_id"]] = {
            "instance_id": device["instance_id"],
            "device_type": device["device_type"],
            "default_params": device["default_params"],
            "simulation_params": device["simulation_params"]
        }
    return {
        "devices": device_configs,
        "topology": scene["simulation_config"].get("topology", []),
        "workflow": scene["simulation_config"].get("workflow", [])
    }
```

### 2. analyze_topology

拓扑排序，确定执行顺序：

```python
@tool
def analyze_topology(topology: list[dict]) -> dict:
    """对设备拓扑关系进行分析，返回执行顺序和依赖关系"""
    # Kahn 算法拓扑排序
    graph = defaultdict(list)
    in_degree = defaultdict(int)
    for edge in topology:
        if edge["to"] != "end":
            graph[edge["from"]].append(edge["to"])
            in_degree[edge["to"]] += 1
    
    queue = [n for n in graph if in_degree[n] == 0]
    order = []
    while queue:
        node = queue.pop(0)
        order.append(node)
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    
    return {
        "execution_order": order,
        "parallel_groups": compute_parallel_groups(topology)
    }
```

### 3. select_device_algorithm

根据设备类型选择轨迹算法：

```python
ALGORITHM_REGISTRY = {
    "conveyor": ["continuous_transport", "batch_transport"],
    "lift": ["lift_xy_trajectory", "lift_single_axis"],
    "storage": ["cell_allocation_fifo", "cell_allocation_priority"],
    "robot": ["pick_and_place_linear", "pick_and_place_arc"]
}

@tool
def select_device_algorithm(device_type: str, user_intent: str) -> dict:
    """根据设备类型和用户意图，选择最合适的轨迹算法"""
    candidates = ALGORITHM_REGISTRY.get(device_type, [])
    selected = candidates[0] if candidates else "default"
    return {
        "device_type": device_type,
        "selected_algorithm": selected,
        "all_candidates": candidates
    }
```

---

## 📊 五种用户输入层级

| 级别 | 输入形式 | Agent 策略 |
|---|---|---|
| Level 1 | "跑一下仿真" | 全依赖 scene.json workflow，参数取默认值 |
| Level 2 | "传送带 400mm/s，跑 30 分钟" | 提取数字参数覆盖默认值 |
| Level 3 | "高峰期场景，仓满后先出库" | Clarifier 追问，生成条件分支协调规则 |
| Level 4 | 上传仿真文档（Markdown 表格） | Doc Parser 解析，注入 SimPy 断言检查 |
| Level 5 | "增加格子到9个，重跑" | MemorySaver 维护状态，支持增量修改 |

---

## 🖥️ Terminal 三阶段输出

```
# 阶段 1：Agent 调度输出（蓝色）
[Agent] 解析场景：6 个设备，5 条拓扑关系
[Agent] 执行顺序：conveyor_1 → smart_storage_1 → storage
[Agent] 算法选择：conveyor_1 → continuous_transport (300mm/s)

# 阶段 2：SimPy 运行输出（绿色时间戳 + 青色设备名）
[  0.00s] conveyor_1      开始执行
[  6.67s] conveyor_1      物料 #1 到达出口
[  6.67s] 信号触发: conveyor_1.part_at_exit
[  7.20s] smart_storage_1 到达取料位

# 阶段 3：统计摘要
══════════════════════════════════════════════════════════
仿真完成  总时长: 3600s
conveyor_1      处理物料: 450 件 | 利用率: 92.3%
smart_storage_1 搬运次数: 448 次 | 平均周期: 7.8s
瓶颈设备: storage（满仓等待 32s）
══════════════════════════════════════════════════════════
```

---

## 🚀 开发优先级

### Week 14: Agent 骨架（最关键）
- SimAgentState TypedDict 定义
- 5 个 @tool 函数编写
- llm.bind_tools(tools) → orchestrator_node
- ToolNode(tools) 接入 StateGraph
- MemorySaver + interrupt_before=["clarifier"]

### Week 15: Plan Generator + SSE
- plan_generator_node（structured_output）
- plan_validator_node（参数校验）
- clarifier_node（interrupt 中断）
- SSE 接口 + astream_events

### Week 16: SimPy 执行层
- WorkshopSimulation 类
- lift_xy_trajectory 算法对接 keyPoints
- 信号事件系统
- ANSI 颜色日志三阶段输出

---

## 📖 详细文档

- [AI 仿真 Agent 详细设计](ai_simulation_agent_design.md) - 完整实现方案

---

## 🔗 相关资源

- **LangGraph**: https://langchain-ai.github.io/langgraph/
- **SimPy**: https://simpy.readthedocs.io/
- **LiteLLM**: https://docs.litellm.ai/
