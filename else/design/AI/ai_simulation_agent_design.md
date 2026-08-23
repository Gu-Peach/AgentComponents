# AI 仿真 Agent 系统架构设计

> 场景驱动 · 调度与执行分离 · LangGraph + SimPy
> 基于 scene.json + 设备配置文件体系

---

## 一、核心架构思想：调度与执行分离

你的判断是准确的——AI 不应该直接做轨迹计算，而是做**仿真调度**。

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
│  ├── ConveyorProcess   → 你的传送带轨迹算法      │
│  ├── LiftProcess       → 你的升降台轨迹算法      │
│  └── StorageProcess    → 你的仓储柜轨迹算法      │
│                                                   │
│  输出：帧数据 → WebSocket → 前端动画             │
│  输出：日志流 → Terminal Panel                   │
└─────────────────────────────────────────────────┘
```

**关键边界：**
- Agent 的职责：读文件、理解场景、决定"什么时候用什么参数做什么"
- 轨迹算法的职责：给定参数，计算具体运动序列（你已经设计好，不变）
- SimPy 的职责：按时序调度各设备进程，驱动事件

---

## 二、Agent 详细架构（LangGraph 状态机）

### 2.1 完整节点图

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

### 2.2 Agent 状态定义

```python
# agents/simulation/state.py
from typing import TypedDict, Annotated, Optional, Literal
from langgraph.graph.message import add_messages

class SimAgentState(TypedDict):
    # ── 输入 ──────────────────────────────────────
    session_id: str
    project_id: str
    user_message: str
    uploaded_docs: list[str]          # 用户上传文档的 MinIO key 列表

    # ── 解析结果 ───────────────────────────────────
    messages: Annotated[list, add_messages]
    intent: Optional[dict]            # 意图解析结果
    input_complexity: Literal["simple", "medium", "detailed"]

    # ── 场景信息 ───────────────────────────────────
    scene_doc: Optional[dict]         # scene.json 内容
    device_configs: dict[str, dict]   # device_id → 设备配置文件内容
    topology_order: list[str]         # 拓扑排序后的执行顺序

    # ── 仿真计划 ───────────────────────────────────
    sim_plan: Optional[dict]          # 结构化仿真计划（见 2.3）
    validation_errors: list[str]
    retry_count: int

    # ── 追问状态 ───────────────────────────────────
    pending_questions: list[str]      # 需要向用户追问的问题
    clarification_answers: dict       # 用户回答的补充参数

    # ── 输出 ───────────────────────────────────────
    task_id: Optional[str]            # Celery 任务 ID
    final_response: str
```

### 2.3 SimPlan 结构（Agent 输出，SimPy 输入）

```python
# 这是 Agent 生成的结构化仿真计划，是两层之间的契约格式

SimPlan = {
    "plan_version": "1.0",
    "scene_id": "project_uuid",
    "sim_config": {
        "duration": 3600,             # 总仿真时长（秒）
        "warm_up": 0,
        "random_seed": 42,
        "speed_multiplier": 1.0
    },

    # 每个设备的执行计划
    "device_plans": [
        {
            "device_id": "conveyor_1",
            "device_type": "conveyor",
            "algorithm": "continuous_transport",   # 选用的轨迹算法名
            "params": {
                # 从设备配置文件提取 + 用户输入覆盖
                "speed": 300,                      # mm/s
                "length": 2000,                    # mm
                "start_offset": 0,
                "end_offset": 50,
                "part_interval": 8.0,              # 每隔 8 秒产生一个物料
            },
            "triggers": {
                "start": "sim_start",              # 仿真开始时立即启动
                "pause_on": [],
                "resume_on": []
            }
        },
        {
            "device_id": "smart_storage_1",
            "device_type": "lift",
            "algorithm": "lift_xy_trajectory",    # 你的升降台轨迹算法
            "params": {
                "root_axis": "x",
                "carrier_axis": "y",
                "root_range": {"min": -4.142, "max": 0.858},
                "carrier_range": {"min": 0.185, "max": 3.160},
                "speed": 0.5,                     # m/s
                "home_position": {"root": 0.858, "carrier": 0.185}
            },
            "triggers": {
                "start": "conveyor_1.part_at_exit",  # 传送带有物料才启动
            }
        },
        {
            "device_id": "storage",
            "device_type": "storage",
            "algorithm": "cell_allocation",
            "params": {
                "cells": [
                    {"id": "A1", "position": {"x": -1.020, "y": 1.595, "z": 0.0}},
                    {"id": "A2", "position": {"x": -1.020, "y": 2.195, "z": 0.0}},
                    {"id": "A3", "position": {"x": -2.040, "y": 2.195, "z": 0.0}}
                ],
                "allocation_strategy": "fifo"     # 先进先出分配
            },
            "triggers": {
                "start": "smart_storage_1.place_done"
            }
        }
    ],

    # 协调规则（拓扑驱动生成）
    "coordination_rules": [
        {
            "type": "signal",
            "when": "conveyor_1.part_at_exit",
            "trigger": "smart_storage_1.fetch_part",
            "description": "传送带出口有物料时，触发升降台取料"
        },
        {
            "type": "signal",
            "when": "smart_storage_1.fetch_done",
            "trigger": "smart_storage_1.place_to_storage",
            "params": {"target": "storage", "strategy": "next_empty_cell"},
            "description": "升降台取料完成后，送往仓储柜空闲格位"
        },
        {
            "type": "resource_wait",
            "resource": "storage.cells",
            "condition": "has_empty",
            "blocked_device": "smart_storage_1",
            "description": "仓储柜满时升降台等待"
        }
    ],

    # Agent 生成的自然语言说明（显示在 Terminal 顶部）
    "plan_summary": "本次仿真模拟智能仓储流水线，传送带以 300mm/s 速度持续输送物料，..."
}
```

---

## 三、Skills 系统设计

每个 Skill 是一个可复用的工具函数，Agent 通过 LangGraph ToolNode 调用。

```python
# agents/simulation/skills/

# ── Skill 1: 场景文件读取 ──────────────────────────────────
@tool
async def read_scene_config(project_id: str) -> dict:
    """
    读取场景配置文件（scene.json）和所有设备配置文件。
    返回完整的场景描述，包括设备列表、拓扑关系、工作流。
    """
    mongo = await get_mongo_db()
    scene = await mongo.scenes.find_one({"_id": project_id})

    # 加载每个设备的完整配置
    device_configs = {}
    for device in scene["devices"]:
        instance_id = device["instance_id"]
        device_configs[device["layout_device_id"]] = {
            "instance_id": instance_id,
            "device_type": device["device_type"],
            "default_params": device["default_params"],
            "simulation_params": device["simulation_params"],
        }

    return {
        "scene_name": scene["name"],
        "description": scene.get("description", ""),
        "devices": device_configs,
        "topology": scene["simulation_config"].get("topology", []),
        "workflow": scene["simulation_config"].get("workflow", []),
        "connections": scene["connections"],
    }


# ── Skill 2: 拓扑排序 ──────────────────────────────────────
@tool
def analyze_topology(topology: list[dict]) -> dict:
    """
    对设备拓扑关系进行分析，返回：
    - 执行顺序（拓扑排序）
    - 设备间的依赖关系
    - 可能的并行执行组
    """
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

    # 找出可并行的设备组（同一拓扑层级）
    parallel_groups = compute_parallel_groups(topology)

    return {
        "execution_order": order,
        "parallel_groups": parallel_groups,
        "critical_path": find_critical_path(topology),
    }


# ── Skill 3: 设备算法选择 ──────────────────────────────────
ALGORITHM_REGISTRY = {
    "conveyor":     ["continuous_transport", "batch_transport", "accumulate_transport"],
    "lift":         ["lift_xy_trajectory", "lift_single_axis"],
    "storage":      ["cell_allocation_fifo", "cell_allocation_priority"],
    "robot":        ["pick_and_place_linear", "pick_and_place_arc"],
}

@tool
def select_device_algorithm(device_type: str, user_intent: str) -> dict:
    """
    根据设备类型和用户意图，选择最合适的轨迹算法。
    返回算法名称和算法描述。
    """
    candidates = ALGORITHM_REGISTRY.get(device_type, [])
    # 简单规则匹配（可替换为 LLM 判断）
    selected = candidates[0] if candidates else "default"
    return {
        "device_type": device_type,
        "selected_algorithm": selected,
        "all_candidates": candidates,
    }


# ── Skill 4: 参数提取与合并 ────────────────────────────────
@tool
def resolve_device_params(
    device_config: dict,
    user_overrides: dict,
    algorithm: str
) -> dict:
    """
    合并设备配置文件中的仿真参数 + 用户输入的覆盖参数。
    验证参数完整性，返回缺失的必要参数列表。
    """
    base_params = device_config.get("simulation_params", {})
    merged = deep_merge(base_params, user_overrides)

    required = ALGORITHM_REQUIRED_PARAMS.get(algorithm, [])
    missing = [k for k in required if k not in merged]

    return {
        "merged_params": merged,
        "missing_params": missing,
        "is_complete": len(missing) == 0,
    }


# ── Skill 5: 协调规则生成 ──────────────────────────────────
@tool
def generate_coordination_rules(
    topology: list[dict],
    device_plans: list[dict]
) -> list[dict]:
    """
    根据拓扑关系，自动生成设备间的信号触发和资源等待规则。
    """
    rules = []
    for edge in topology:
        if edge["relation"] == "feeds":
            rules.append({
                "type": "signal",
                "when": f"{edge['from']}.part_at_exit",
                "trigger": f"{edge['to']}.fetch_part",
                "description": edge["description"],
            })
        elif edge["relation"] == "manipulates":
            rules.append({
                "type": "signal",
                "when": f"{edge['from']}.operation_done",
                "trigger": f"{edge['to']}.receive",
                "description": edge["description"],
            })
    return rules
```

---

## 四、SimPy 执行层设计

```python
# simulation/workshop_sim.py

import simpy
import json
from simulation.algorithms import ALGORITHM_MAP

class WorkshopSimulation:
    """
    接收 Agent 生成的 SimPlan，用 SimPy 执行仿真。
    与 Agent 层完全解耦——只认 SimPlan JSON 格式。
    """

    def __init__(self, sim_plan: dict, log_callback, frame_callback):
        self.plan = sim_plan
        self.log = log_callback        # 输出到 Terminal
        self.frame = frame_callback    # 输出到 3D 动画
        self.env = simpy.Environment()
        self.events: dict[str, simpy.Event] = {}   # 信号事件表
        self.resources: dict = {}                   # 共享资源表

    def setup(self):
        # 预创建所有信号事件
        all_signals = self._collect_signals()
        for sig in all_signals:
            self.events[sig] = self.env.event()

        # 为每个设备启动 SimPy 进程
        for device_plan in self.plan["device_plans"]:
            algo_name = device_plan["algorithm"]
            algo_fn = ALGORITHM_MAP[algo_name]          # 你的轨迹算法

            self.env.process(
                self._device_process(device_plan, algo_fn)
            )

        # 协调进程（监听信号，触发事件）
        self.env.process(self._coordinator())

    async def _device_process(self, plan: dict, algo_fn):
        """每个设备的 SimPy 进程"""
        device_id = plan["device_id"]

        # 等待启动触发信号
        start_trigger = plan["triggers"].get("start", "sim_start")
        if start_trigger != "sim_start":
            yield self.events[start_trigger]

        self.log(f"\x1b[32m[{self.env.now:.2f}s]\x1b[0m "
                 f"\x1b[36m{device_id}\x1b[0m 开始执行")

        # 调用你的轨迹算法（持续运行或单次）
        while True:
            # 算法返回一系列轨迹关键帧
            trajectory = algo_fn(plan["params"], self.env.now)

            for keyframe in trajectory:
                # 推进仿真时间到下一关键帧
                yield self.env.timeout(keyframe["dt"])

                # 发送帧数据到前端
                self.frame({
                    "sim_time": self.env.now,
                    "device_id": device_id,
                    "state": keyframe["state"],
                    "position": keyframe.get("position"),
                    "joints": keyframe.get("joints"),
                })

                # 触发状态变化信号
                if "emit_signal" in keyframe:
                    sig = f"{device_id}.{keyframe['emit_signal']}"
                    if sig in self.events and not self.events[sig].triggered:
                        self.events[sig].succeed()
                        self.log(f"\x1b[33m[{self.env.now:.2f}s]\x1b[0m "
                                 f"信号触发: \x1b[35m{sig}\x1b[0m")

            # 单次设备（如 lift）完成后退出循环
            if not plan.get("continuous", False):
                break

    async def _coordinator(self):
        """协调进程：监控协调规则，处理资源等待"""
        for rule in self.plan["coordination_rules"]:
            if rule["type"] == "signal":
                # 等待触发条件
                yield self.events.get(rule["when"], self.env.event().succeed())
                # 触发目标信号
                target_sig = rule["trigger"]
                if target_sig in self.events:
                    self.events[target_sig].succeed()

    def run(self):
        self.setup()
        config = self.plan["sim_config"]

        # 打印计划摘要到终端
        self.log(f"\x1b[1m\x1b[34m{'='*50}\x1b[0m")
        self.log(f"\x1b[1m仿真计划: {self.plan.get('plan_summary', '')}\x1b[0m")
        self.log(f"\x1b[34m{'='*50}\x1b[0m")
        self.log(f"总时长: {config['duration']}s | "
                 f"速度: {config['speed_multiplier']}x | "
                 f"种子: {config['random_seed']}")

        self.env.run(until=config["duration"])

        # 输出统计结果
        self._print_stats()

    def _print_stats(self):
        self.log(f"\n\x1b[1m\x1b[32m{'='*50}\x1b[0m")
        self.log(f"\x1b[1m\x1b[32m仿真完成\x1b[0m")
        # 各设备统计...
```

---

## 五、Terminal 输出格式设计

终端输出分三个阶段，每个阶段有固定的 ANSI 颜色规范：

```
# ── 阶段 1：Agent 调度输出（仿真开始前）────────────────────

══════════════════════════════════════════════════════════
仿真计划：智能仓储流水线
══════════════════════════════════════════════════════════
[Agent] 解析场景：6 个设备，5 条拓扑关系
[Agent] 执行顺序：conveyor_1 → smart_storage_1 → storage → smart_storage_2 → conveyor_2
[Agent] 算法选择：
        ├── conveyor_1       → continuous_transport (speed=300mm/s)
        ├── smart_storage_1  → lift_xy_trajectory (speed=0.5m/s)
        ├── storage          → cell_allocation_fifo (3 cells)
        ├── smart_storage_2  → lift_xy_trajectory (speed=0.5m/s)
        └── conveyor_2       → continuous_transport (speed=250mm/s)
[Agent] 协调规则：5 条信号触发，1 条资源等待
══════════════════════════════════════════════════════════


# ── 阶段 2：SimPy 运行输出（仿真过程中）───────────────────

[  0.00s] conveyor_1     开始执行
[  0.00s] conveyor_1     物料 #1 进入传送带
[  6.67s] conveyor_1     物料 #1 到达出口
[  6.67s] 信号触发: conveyor_1.part_at_exit
[  6.67s] smart_storage_1 开始执行 → 移动至取料位
[  7.20s] smart_storage_1 到达取料位 (x=0.858, y=0.185)
[  7.20s] smart_storage_1 夹取物料 #1
[  8.50s] smart_storage_1 移动至格位 A1 (x=-1.020, y=1.595)
[  8.50s] 信号触发: smart_storage_1.place_done
[  8.50s] storage        格位 A1 ← 物料 #1 [已占用: 1/3]
[ 13.33s] conveyor_1     物料 #2 到达出口
...


# ── 阶段 3：统计摘要（仿真结束后）─────────────────────────

══════════════════════════════════════════════════════════
仿真完成  总时长: 3600s
══════════════════════════════════════════════════════════
设备统计：
  conveyor_1      处理物料: 450 件 | 利用率: 92.3%
  smart_storage_1 搬运次数: 448 次 | 平均周期: 7.8s
  storage         峰值占用: 3/3   | 满仓次数: 12 次
  smart_storage_2 搬运次数: 440 次 | 平均周期: 8.1s
  conveyor_2      处理物料: 440 件 | 利用率: 88.6%

系统吞吐量: 440 件/小时
瓶颈设备:   storage (满仓导致 32s 等待)
══════════════════════════════════════════════════════════
```

ANSI 颜色规范：
```python
COLORS = {
    "agent":    "\x1b[34m",    # 蓝色   → Agent 调度信息
    "sim_time": "\x1b[32m",    # 绿色   → 仿真时间戳
    "device":   "\x1b[36m",    # 青色   → 设备名称
    "signal":   "\x1b[35m",    # 紫色   → 信号触发
    "warn":     "\x1b[33m",    # 黄色   → 等待/警告
    "error":    "\x1b[31m",    # 红色   → 错误
    "bold":     "\x1b[1m",     # 粗体
    "reset":    "\x1b[0m",     # 重置
}
```

---

## 六、用户输入案例库（从简单到详细）

### Level 1：极简输入（一句话）

```
用户：运行一下仿真
用户：模拟这个流水线
用户：跑一遍看看
```

**Agent 行为：**
- 完全依赖 scene.json 中的 workflow 和 topology 推断意图
- 所有参数取 device_specs 默认值
- 仿真时长取默认 3600s

---

### Level 2：简单参数输入（带关键数字）

```
用户：传送带速度 400mm/s，升降台速度 0.8m/s，跑 10 分钟
用户：仿真 30 分钟，看看仓储柜能存多少件
用户：用快速模式跑，速度倍率调到 5x
用户：入库格子用 A1 A2 B1，出库按照入库顺序
```

**Agent 行为：**
- 提取用户给出的参数，覆盖默认值
- 其余参数仍从配置文件读取
- 快速校验参数范围（速度不超过设备限制）

---

### Level 3：中等复杂度（有工艺逻辑）

```
用户：模拟高峰期场景，传送带满负荷（500mm/s），
      升降台优先填满上层格子（A3、B3），
      当仓储柜满了之后，升降台2先出库最老的物料，
      再让升降台1继续入库，仿真 1 小时。

用户：测试升降台1和升降台2同时工作的情况，
      升降台1负责 A 列，升降台2负责 B 列，
      两台不能同时访问同一排，看看会不会死锁。

用户：物料每隔 10 秒一件，前 20 分钟只入库，
      后 40 分钟一边入库一边出库，
      统计最终仓储柜利用率。
```

**Agent 行为：**
- 需要 Param Resolver 提取多个复合参数
- 协调规则生成需要考虑条件分支（满仓逻辑、列分工）
- 可能需要 Clarifier 追问：「出库策略是 FIFO 还是指定格位？」

---

### Level 4：详细文档输入（上传文件）

用户上传一份 Markdown 或 TXT 文档：

```markdown
# 仿真测试方案 v2.0
## 测试目标
验证智能仓储系统在高吞吐量场景下的稳定性

## 设备参数
| 设备 | 参数 | 数值 |
|------|------|------|
| conveyor_1 | 速度 | 500 mm/s |
| conveyor_1 | 物料间隔 | 8s |
| smart_storage_1 | 速度 | 0.8 m/s |
| smart_storage_2 | 速度 | 0.6 m/s |

## 入库规则
- 优先填 A 列（A1→A2→A3）
- A 列满后填 B 列
- 禁止同时对同一列进行入库和出库

## 出库规则
- 接到出库指令后，从 B 列开始取（LIFO）
- 出库触发条件：仓储柜 A 列全满

## 仿真时长
- 总时长：2 小时
- 记录间隔：每 5 分钟输出一次统计

## 验收标准
- 系统不出现死锁
- 吞吐量 ≥ 400 件/小时
- 升降台等待时间 < 总时长的 10%
```

**Agent 行为：**
- Doc Parser 解析表格、规则、约束
- 生成带条件分支的复杂协调规则
- 将验收标准注入 SimPy 断言检查
- 每 5 分钟输出一次中间统计到 Terminal

---

### Level 5：对话式迭代（多轮调整）

```
轮次 1：
用户：跑一下仿真
Agent：[执行完成] 吞吐量 380 件/小时，瓶颈是仓储柜满仓（12次）

轮次 2：
用户：增加仓储格子到 9 个（3×3），重新跑
Agent：[更新 storage cells 配置，重新执行]

轮次 3：
用户：还是满仓，能不能让升降台 2 更快一点
Agent：smart_storage_2 当前速度 0.5m/s，设备限制最高 2.0m/s，
       调整到多少合适？
用户：先试试 1.0m/s
Agent：[更新参数，重新执行]

轮次 4：
用户：好多了，把这个配置保存为方案 B，再试试速度 1.5 的
```

**Agent 行为：**
- 维护多轮对话的参数状态
- 支持增量修改（只改变更新的参数）
- 支持命名保存仿真方案（写入 MongoDB agent_messages）

---

## 七、Agent 节点实现（关键节点代码）

```python
# agents/simulation/nodes/intent_parser.py

INTENT_PARSER_PROMPT = """
你是工业仿真系统的助手。分析用户的仿真请求，判断：

1. input_complexity: 
   - "simple": 用户只说"跑一下"或类似极简指令
   - "medium": 用户给出了部分参数或简单规则
   - "detailed": 用户上传了文档或给出完整的仿真方案

2. extracted_params: 用户明确给出的参数（设备→参数→值 的映射）
3. missing_info: 你认为需要但用户没有给出的信息（如果 simple 则为空）
4. sim_intent: 用户的仿真目标（性能测试/功能验证/参数调优）

仅返回 JSON，不要有其他文字。
"""

async def intent_parser_node(state: SimAgentState) -> dict:
    llm = get_llm().with_structured_output(IntentResult)
    result = await llm.ainvoke([
        SystemMessage(content=INTENT_PARSER_PROMPT),
        HumanMessage(content=state["user_message"]),
    ])
    return {
        "intent": result.model_dump(),
        "input_complexity": result.input_complexity,
    }


# agents/simulation/nodes/plan_generator.py

PLAN_GENERATOR_PROMPT = """
你是仿真计划生成专家。根据以下信息，生成结构化的 SimPlan：

场景信息：{scene_doc}
拓扑分析：{topology_analysis}
用户参数：{resolved_params}
工作流描述：{workflow}

要求：
1. 为每个设备选择合适的轨迹算法
2. 根据拓扑关系生成设备间的协调规则
3. 所有参数必须在设备约束范围内
4. 生成清晰的计划摘要（中文，50字以内）

仅输出 JSON 格式的 SimPlan，不要有其他文字。
"""

async def plan_generator_node(state: SimAgentState) -> dict:
    llm = get_llm().with_structured_output(SimPlanSchema)
    scene = state["scene_doc"]
    plan = await llm.ainvoke([
        SystemMessage(content=PLAN_GENERATOR_PROMPT.format(
            scene_doc=json.dumps(scene, ensure_ascii=False),
            topology_analysis=json.dumps(state["topology_order"], ensure_ascii=False),
            resolved_params=json.dumps(state.get("clarification_answers", {}), ensure_ascii=False),
            workflow=json.dumps(scene.get("workflow", []), ensure_ascii=False),
        )),
    ])
    return {"sim_plan": plan.model_dump()}
```

---

## 八、与 smart_storage_1.json 的对接

你的设备配置文件中有 `keyPoints` 字段（如 `transfer_board`），
这是轨迹算法的关键对接点：

```python
# simulation/algorithms/lift_xy_trajectory.py

def lift_xy_trajectory(params: dict, start_time: float):
    """
    升降台 XY 双轴轨迹算法。
    keyPoints 中的 transfer_board 是取料/放料的停靠点。
    """
    key_points = params.get("key_points", [])
    transfer_board = next(
        (kp for kp in key_points if kp["name"] == "transfer_board"), None
    )
    root_range = params["root_range"]
    carrier_range = params["carrier_range"]
    speed = params["speed"]

    def move_to(current_pos, target_pos):
        """计算运动到目标位置的时间和关键帧"""
        root_dist = abs(target_pos["root"] - current_pos["root"])
        carrier_dist = abs(target_pos["carrier"] - current_pos["carrier"])
        # 水平和竖直同时运动（如果设备支持）
        dt = max(root_dist, carrier_dist) / speed
        return dt, target_pos

    trajectory = []
    current = {"root": params["home_position"]["root"],
               "carrier": params["home_position"]["carrier"]}

    # 1. 移动到传送带取料点
    dt, current = move_to(current, {
        "root": root_range["max"],
        "carrier": carrier_range["min"]
    })
    trajectory.append({
        "dt": dt,
        "state": "moving_to_pickup",
        "position": current,
        "emit_signal": None,
    })

    # 2. 夹取物料
    trajectory.append({
        "dt": 0.5,    # 夹取动作固定 0.5s
        "state": "picking",
        "position": current,
        "emit_signal": "fetch_done",
    })

    # 3. 移动到目标格位（由 SimPlan 协调规则提供 target_cell）
    # ... 继续生成帧序列

    return trajectory
```

---

## 九、实现优先级

```
Week 1   Skills 基础层
         - read_scene_config（读 scene.json + 设备配置）
         - analyze_topology（拓扑排序）
         - select_device_algorithm（算法注册表）

Week 2   Plan Generator
         - 简单场景（Level 1 输入）的完整 SimPlan 生成
         - SimPlan → SimPy 执行的串联

Week 3   SimPy 执行层
         - lift_xy_trajectory 算法对接
         - Terminal 日志输出（ANSI 着色）
         - WebSocket 帧数据推送

Week 4   复杂场景支持
         - Level 3 输入的协调规则生成
         - Clarifier 追问节点
         - 多轮对话状态维护

Week 5   Doc Parser + 统计报表
         - Level 4 文档输入解析
         - 仿真统计摘要生成
         - 仿真方案保存/加载
```
