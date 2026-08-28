# 后端接口、数据库与 Agent 系统设计方案

> 版本：v0.2  
> 日期：2026-08-19  
> 适用背景：前端已基于 Three.js / R3F 实现场景编辑与展示；当前重点转向后端接口、场景数据结构、数据库选型、拓扑理解与 Agent 调度规划。

> 拆分说明：本文件保留为总览和历史背景。后续实现请优先阅读 `docs/backend/README.md`、`docs/backend/backend_api_design.md`、`docs/backend/agent_runtime_design.md`、`docs/backend/data_model_database_design.md`。

---

## 1. 核心判断

本系统的后端不应只做普通 CRUD，也不应把 Agent 拆成固定的“三阶段 Agent”。更合理的设计是：

1. **后端先建立稳定的场景事实层**：设备、位姿、端口、连接、参数、资产、版本必须有统一 schema。
2. **拓扑理解是确定性能力，不是 LLM 猜测能力**：端口世界坐标、显式连接、隐式候选边、连通分量、可达性、环路、悬空端口都应由代码计算。
3. **Agent 是一个可中断、可恢复、可修订的状态机**：LLM 负责理解用户意图、生成候选计划和解释结果；数据库、拓扑、校验、patch、仿真提交全部通过工具完成。
4. **用户输入不是一次性的**：用户会在 Agent 执行中追加约束、否定方案、改变设备、暂停仿真或取消任务，因此 Agent Run 必须支持 interrupt / revise / resume / cancel。
5. **场景修改必须走 patch 与 revision 机制**：Agent 不直接覆盖当前场景，而是生成基于某个 `scene_revision` 的候选 patch；写入时做版本校验，冲突则重载场景并重规划或要求用户确认。
6. **仿真执行和 Agent 决策解耦**：Agent 输出 `SimPlan`；仿真 worker 只消费结构化计划并持续产生日志、帧、指标和 observation。
7. **场景由单个设备实例组合而成**：后端接口必须以 `DeviceInstance` 为基本 CRUD 单位，场景只是实例、连接、流程和运行配置的容器。
8. **接口必须分层建模**：前端当前已有真实接口和流程层接口；后端应把真实接口、流程接口、信号接口统一纳入设备规范，并负责最终校验和编译。
9. **开发期优先使用本地 Supabase**：当前资产主要是 GLB 文件，本地开发可以用 Supabase Postgres + Supabase Storage 替代自建 PostgreSQL + MinIO；Redis 只保存运行时状态、队列和事件流，不保存必须长期持久化的数据。

---

## 2. 系统需要实现的能力全景

### 2.1 项目与资产能力

- 用户、项目、成员权限。
- 设备资产目录：GLB、URDF、缩略图、设备类型、制造商、标签。
- 设备规范库：参数 schema、端口模板、动作模板、仿真约束、默认算法。
- 布局模板：可复用的产线或工位布局。
- 文件存储：模型、贴图、URDF 依赖网格、用户上传文档、导出结果。

### 2.2 场景编辑能力

- 保存前端 Three.js 场景中的设备实例、位姿、缩放、名称、可见性、锁定状态。
- 支持 JSON Patch / command patch 更新设备、参数、连接、流程。
- 支持场景 revision，保证多人协同和 Agent 写入不互相覆盖。
- 支持场景事件流：`device_added`、`device_moved`、`params_updated`、`port_connected`、`edge_confirmed`。
- 支持从当前场景导出 `SceneDocument`，作为 Agent 和仿真统一输入。

### 2.3 拓扑理解能力

- 根据设备规范中的端口模板和实例 transform，计算端口世界坐标、方向和兼容性。
- 读取显式连接：用户手动连接或导入布局中已有连接。
- 推断隐式候选连接：基于空间距离、端口方向、端口类型、物料类型、设备语义打分。
- 生成 `DeviceTopologyGraph`：节点、端口、边、连通分量、拓扑序、候选边、异常列表。
- 识别问题：孤立设备、悬空端口、方向冲突、类型不兼容、环路、不可达目标。
- 将拓扑摘要转换成 Agent 可读上下文，但不让 LLM 自己遍历图。

### 2.4 Agent 能力

- 理解自然语言输入：运行仿真、配置工艺、修改参数、连接设备、查询场景、诊断拓扑。
- 读取当前场景、拓扑、设备规范、历史计划和用户偏好。
- 生成候选计划：场景 patch、工艺配置、连接建议、SimPlan。
- 调用确定性工具：拓扑构建、可达性校验、参数校验、patch 预演、仿真提交。
- 支持执行中用户打断：追加约束、局部修改、暂停、取消、恢复、重新规划。
- 输出可审计事件：当前节点、读取了什么、生成了什么、等待什么、应用了哪些 patch。

### 2.5 仿真与运行时能力

- 将 Agent 生成的 `SimPlan` 提交给仿真 worker。
- 支持启动、暂停、恢复、停止、重跑、基于当前状态重规划。
- 输出实时日志、帧数据、设备状态、物料位置、资源占用、统计指标。
- 支持 observation 回流给 Agent：仿真超时、死锁、资源冲突、目标未达成时触发修复或重规划。

---

## 3. 推荐技术栈

### 3.1 后端服务

| 层级 | 推荐技术 | 原因 |
|---|---|---|
| API 服务 | FastAPI + Uvicorn | Python 生态适合 Agent / SimPy；FastAPI 原生支持 OpenAPI、WebSocket、依赖注入。 |
| Schema | Pydantic v2 | 统一请求、响应、场景文档、Agent 状态、SimPlan 校验。 |
| ORM | SQLAlchemy 2.x async / SQLModel | 管理 PostgreSQL 结构化表。 |
| Agent Runtime | LangGraph | 用作有状态图运行时，支持 checkpoint、interrupt、resume，不采用自由 ReAct 循环。 |
| LLM 接入 | LiteLLM 或 OpenAI-compatible client | 统一不同模型供应商，便于切换云模型和本地模型。 |
| 仿真 | SimPy + 自研设备算法 | 离散事件调度；轨迹计算保持确定性。 |
| 异步任务 | Celery / Dramatiq + Redis | 长时间仿真、文档解析、拓扑重算等任务从 API 主进程剥离。 |
| 实时通道 | WebSocket + Redis Pub/Sub / Streams | 场景协同、仿真帧、终端日志、Agent 事件推送。 |

### 3.2 数据库与存储

推荐第一阶段采用：**Supabase 本地开发栈 + Redis**。

更具体地说：

- 开发期：使用 `supabase start` 启动本地 Supabase，直接获得 PostgreSQL、Auth、Storage、Studio、Realtime 等能力。
- 生产期：可以继续使用托管 Supabase，也可以迁移为自管 PostgreSQL + S3/MinIO + 独立 Auth/Realtime。
- Redis：只用于运行时状态、任务队列、分布式锁、事件流和仿真帧缓存，不保存必须长期存在的场景、计划、设备规范或审计数据。

当前模型资产实际只有 GLB 文件时，不必第一阶段单独引入 MinIO。Supabase Storage 足够承担 GLB、缩略图、用户上传文档和导出文件；后续如果要支持大量 URDF 依赖网格、贴图包、企业私有对象存储，再把 Storage adapter 抽象出来切到 S3/MinIO。

不建议第一阶段同时引入 PostgreSQL + MongoDB 双主存储，除非团队已经有成熟的 MongoDB 运维和数据一致性方案。原因是场景、Agent run、计划版本、patch、权限、资产索引之间存在大量一致性约束，单一 PostgreSQL 主库更容易保证事务、审计和版本冲突处理。

| 存储 | 用途 | 说明 |
|---|---|---|
| Supabase PostgreSQL | 主数据、场景、设备规范、Agent run、SimPlan、审计事件 | JSONB 保存可变 schema；关系表保存权限、索引和引用；后续可加 pgvector。 |
| Supabase Storage | GLB、缩略图、上传文档、导出文件 | 开发期替代 MinIO；数据库只保存 bucket/path 和元数据。 |
| Redis | 在线状态、run 状态、事件流、仿真帧缓存、分布式锁 | 不作为长期事实来源。 |
| MinIO / S3 | 生产期可选对象存储 | 当资产规模、权限隔离或部署形态要求独立对象存储时再引入。 |

### 3.3 本地开发环境建议

第一阶段建议本地只启动三个核心依赖：

```text
Supabase local
  - PostgreSQL: 事实库、JSONB、pgvector 预留
  - Storage: GLB / thumbnail / upload / export
  - Auth: 可先用，后续也可替换
  - Studio: 方便查看数据

Redis local
  - Agent run ephemeral state
  - simulation frame stream
  - task queue / lock

FastAPI backend
  - Scene / Topology / Agent / Simulation API
```

注意：Redis 里的任何数据都应可从 PostgreSQL 的事实数据或仿真任务重新生成。比如 `topology:{scene_id}:{revision}` 可以缓存，但 canonical topology 结果仍应写入 `scene_topologies`，否则 Agent 审计和任务恢复会不稳定。

第二阶段可选增强：

- 如果设备文档、场景快照和 Agent trace 体量巨大，可把历史快照归档到对象存储或 ClickHouse。
- 如果需要全文 + 向量混合检索，可先用 PostgreSQL `pgvector`，规模上来后再考虑独立向量库或 MongoDB Atlas Search / Vector Search。
- 如果需要非常复杂的图查询，可将 `DeviceTopologyGraph` 另存到图数据库；第一阶段不建议引入。

---

## 4. 数据模型设计

### 4.1 单位和坐标约定

所有后端 canonical schema 统一使用 SI 单位：

- 长度：米 `m`
- 角度：弧度 `rad`
- 时间：秒 `s`
- 速度：`m/s` 或 `rad/s`
- 坐标系：右手系，字段中明确 `coordinate_system`

如果前端 UI 展示毫米、角度制或设备厂商单位，必须在 API 边界转换，避免 Agent 和仿真层混用单位。

### 4.2 三层接口模型

当前前端已经区分了两类接口：

- **物理/真实接口**：来自设备配置中的 `interfaceConfig.interfaces`、`transfer.from/to`，用于坐标提取、设备对齐、执行参数生成。
- **流程层接口 / 工艺流程口**：Interface 画布展示给用户连线的抽象接口，只暴露 `flow_input / flow_output`，连接关系保存 `sourceInterface / targetInterface`。

后端方案应在此基础上补齐第三类接口：**信号接口**。三类接口都应该存在于后端 `DeviceSpec`，但前端不需要全部暴露给普通用户。

| 接口层 | 面向对象 | 是否有几何坐标 | 是否给用户直接连线 | 后端职责 | 前端职责 |
|---|---|---:|---:|---|---|
| 物理接口 `physical_interfaces` | 仿真执行、设备对齐、真实端口 | 是 | 默认否，可调试模式显示 | 保存接口定义、解析世界坐标、映射到执行算法 | 从 GLB 节点/配置中读取锚点，必要时辅助可视化 |
| 流程接口 `process_ports` | 工艺流程编排、用户可理解连线 | 否或弱几何 | 是 | 校验 `flow_output -> flow_input`，编译为物理接口链路 | Interface 画布展示 Input/Output，限制基础连线规则 |
| 信号接口 `signal_ports` | 控制事件、传感器、触发条件 | 通常否 | 第二阶段再显示 | 建模事件输入/输出，生成 SimPlan trigger / effect | 后续可做高级控制面板 |

关键决策：

1. **前端可以实现交互约束，但不能成为接口语义的唯一事实来源**。例如 UI 限制 `flow_output -> flow_input` 是正确的，但后端仍必须重复校验，因为 Agent、导入文件、协同编辑都可能绕过 UI。
2. **真实接口不应直接暴露给普通流程编排用户**。用户只看到“输入/输出”即可；真实接口用于后端把流程连接编译成执行锚点。
3. **信号接口先进入数据模型，不急于进入 UI**。当前主要做物料流，后续做传感器、阻塞、握手、PLC-like 逻辑时，信号接口会成为 SimPlan 的触发条件。
4. **流程连接和物理连接分开保存**。流程连接是用户意图，物理连接是执行解析结果；二者可以一对多、多对一或需要设备适配器转换。

推荐接口字段：

```json
{
  "physical_interfaces": [
    {
      "interface_id": "entry",
      "label": "Entry",
      "kind": "material",
      "direction": "input",
      "node_name": "Entry_Anchor",
      "local_position": [-1.0, 0.0, 0.4],
      "local_forward": [-1.0, 0.0, 0.0],
      "material_classes": ["box", "pallet"],
      "role": "transfer.from"
    },
    {
      "interface_id": "exit",
      "label": "Exit",
      "kind": "material",
      "direction": "output",
      "node_name": "Exit_Anchor",
      "local_position": [1.0, 0.0, 0.4],
      "local_forward": [1.0, 0.0, 0.0],
      "material_classes": ["box", "pallet"],
      "role": "transfer.to"
    }
  ],
  "process_ports": [
    { "port_id": "flow_input", "direction": "input", "label": "Input" },
    { "port_id": "flow_output", "direction": "output", "label": "Output" }
  ],
  "signal_ports": [
    { "port_id": "part_ready", "direction": "output", "event_type": "material_detected" },
    { "port_id": "start", "direction": "input", "event_type": "command" }
  ],
  "interface_bindings": [
    { "process_port": "flow_input", "physical_interface": "entry" },
    { "process_port": "flow_output", "physical_interface": "exit" },
    { "signal_port": "part_ready", "emitted_by": "physical_interface.exit" }
  ]
}
```

### 4.3 DeviceSpec：设备规范

`DeviceSpec` 是 Agent、属性面板、拓扑推断、仿真计划的共同约束来源。

```json
{
  "spec_id": "spec_conveyor_belt_v1",
  "device_type": "conveyor",
  "version": "1.0.0",
  "display_name": "Standard Belt Conveyor",
  "asset_defaults": {
    "model_format": "glb",
    "model_key": "models/conveyor/standard_belt.glb"
  },
  "param_schema": {
    "length_m": { "type": "number", "min": 0.2, "max": 20.0, "default": 2.0 },
    "width_m": { "type": "number", "min": 0.1, "max": 3.0, "default": 0.6 },
    "speed_mps": { "type": "number", "min": 0.01, "max": 3.0, "default": 0.3 }
  },
  "physical_interfaces": [
    {
      "interface_id": "entry",
      "direction": "input",
      "kind": "material",
      "local_position": [-1.0, 0.0, 0.4],
      "local_forward": [-1.0, 0.0, 0.0],
      "material_classes": ["box", "pallet"],
      "capacity": 1
    },
    {
      "interface_id": "exit",
      "direction": "output",
      "kind": "material",
      "local_position": [1.0, 0.0, 0.4],
      "local_forward": [1.0, 0.0, 0.0],
      "material_classes": ["box", "pallet"],
      "capacity": 1
    }
  ],
  "process_ports": [
    { "port_id": "flow_input", "direction": "input", "label": "Input" },
    { "port_id": "flow_output", "direction": "output", "label": "Output" }
  ],
  "signal_ports": [
    { "port_id": "start", "direction": "input", "event_type": "command" },
    { "port_id": "done", "direction": "output", "event_type": "action_completed" }
  ],
  "interface_bindings": [
    { "process_port": "flow_input", "physical_interface": "entry" },
    { "process_port": "flow_output", "physical_interface": "exit" },
    { "signal_port": "done", "emitted_by": "physical_interface.exit" }
  ],
  "actions": [
    {
      "action_type": "transport",
      "required_ports": ["entry", "exit"],
      "default_algorithm": "continuous_transport",
      "preconditions": ["input_available", "output_not_blocked"],
      "effects": ["material_at_exit"]
    }
  ]
}
```

### 4.4 SceneDocument：场景事实

```json
{
  "scene_id": "scene_01",
  "project_id": "project_01",
  "schema_version": "scene/v1",
  "revision": 42,
  "unit": "m",
  "coordinate_system": "threejs-y-up",
  "instances": [
    {
      "instance_id": "conveyor_1",
      "spec_id": "spec_conveyor_belt_v1",
      "device_type": "conveyor",
      "name": "Conveyor 1",
      "transform": {
        "position": [0.0, 0.0, 0.0],
        "rotation_euler": [0.0, 0.0, 0.0],
        "scale": [1.0, 1.0, 1.0]
      },
      "params": {
        "length_m": 2.0,
        "width_m": 0.6,
        "speed_mps": 0.3
      },
      "semantic_tags": ["source", "material_flow"],
      "locked": false,
      "visible": true
    }
  ],
  "process_edges": [
    {
      "edge_id": "proc_edge_001",
      "source_instance_id": "conveyor_1",
      "source_interface": "flow_output",
      "target_instance_id": "lift_1",
      "target_interface": "flow_input",
      "edge_type": "material_flow",
      "status": "confirmed",
      "created_by": "user"
    }
  ],
  "physical_edges": [
    {
      "edge_id": "phy_edge_001",
      "from_port": "conveyor_1.exit",
      "to_port": "lift_1.entry",
      "edge_type": "material_transfer",
      "status": "confirmed",
      "source_process_edge_id": "proc_edge_001",
      "created_by": "compiled_from_process_edge"
    }
  ],
  "signal_edges": [
    {
      "edge_id": "sig_edge_001",
      "source_instance_id": "conveyor_1",
      "source_signal": "part_ready",
      "target_instance_id": "lift_1",
      "target_signal": "start",
      "edge_type": "control_signal",
      "status": "planned"
    }
  ],
  "process": {
    "goals": [],
    "workflow_notes": []
  },
  "updated_at": "2026-08-18T00:00:00Z"
}
```

字段说明：

- `instances` 是场景最小组成单元，后端接口应支持单个设备实例的添加、删除、复制、参数更新、transform 更新。
- `process_edges` 对齐前端 Interface 画布：保存 `sourceInterface / targetInterface` 字符串，表达用户可理解的工艺流。
- `physical_edges` 是执行层连接：可以由 `process_edges + interface_bindings` 编译得到，也可以来自用户显式物理对齐/吸附操作。
- `signal_edges` 表示事件触发或控制信号：第一阶段可以仅在 SimPlan 中生成，不一定开放 UI 编辑。
- `process_edges` 是用户意图事实，`physical_edges` 是执行事实；二者不要混为一个 `edges` 字段。

### 4.5 ResolvedPort：运行时端口

后端不要求前端每次保存端口世界坐标。端口世界坐标应由 `DeviceSpec.physical_interfaces + SceneInstance.transform + params` 计算生成。

```json
{
  "port_id": "conveyor_1.exit",
  "instance_id": "conveyor_1",
  "interface_id": "exit",
  "direction": "output",
  "world_position": [1.0, 0.4, 0.0],
  "world_forward": [1.0, 0.0, 0.0],
  "material_classes": ["box", "pallet"],
  "capacity": 1
}
```

### 4.6 DeviceTopologyGraph：拓扑产物

```json
{
  "topology_id": "topo_42",
  "scene_id": "scene_01",
  "input_revision": 42,
  "nodes": [
    { "instance_id": "conveyor_1", "device_type": "conveyor" },
    { "instance_id": "lift_1", "device_type": "lift" }
  ],
  "ports": [],
  "edges": [
    {
      "from_port": "conveyor_1.exit",
      "to_port": "lift_1.entry",
      "kind": "explicit",
      "confidence": 1.0,
      "material_classes": ["box"]
    },
    {
      "from_port": "lift_1.output",
      "to_port": "storage_1.A2",
      "kind": "inferred_candidate",
      "confidence": 0.78,
      "reasons": ["distance_close", "direction_compatible", "material_compatible"]
    }
  ],
  "components": [
    { "component_id": "line_1", "instances": ["conveyor_1", "lift_1", "storage_1"] }
  ],
  "warnings": [
    { "code": "DANGLING_OUTPUT", "port_id": "lift_1.output", "severity": "warning" }
  ],
  "summary_for_agent": "产线 line_1 包含 conveyor_1 -> lift_1 -> storage_1，其中 lift_1.output 到 storage_1.A2 是推断候选，置信度 0.78，尚未确认。"
}
```

---

## 5. PostgreSQL 表设计

### 5.1 核心表

```sql
users
projects
project_members
assets                  -- GLB / URDF / texture / thumbnail 元数据
device_specs            -- 设备规范，param_schema / ports / actions 用 JSONB
scenes                  -- 当前场景快照 current_document JSONB + revision
scene_events            -- 每次场景修改的 append-only event / patch
scene_topologies        -- 拓扑构建结果 JSONB，绑定 scene_revision
agent_threads           -- 一个聊天/任务上下文
agent_runs              -- 一次 Agent 执行
agent_events            -- Agent 事件流，便于审计和回放
agent_artifacts         -- 计划、patch、拓扑摘要、候选答案等中间产物
sim_plans               -- Agent 生成的 SimPlan
simulation_runs         -- 仿真运行记录
simulation_events       -- 低频仿真事件与统计摘要，高频帧不长期入 PG
```

### 5.2 scenes

```sql
CREATE TABLE scenes (
  id UUID PRIMARY KEY,
  project_id UUID NOT NULL REFERENCES projects(id),
  schema_version TEXT NOT NULL DEFAULT 'scene/v1',
  revision BIGINT NOT NULL DEFAULT 0,
  current_document JSONB NOT NULL,
  updated_by UUID,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_scenes_project ON scenes(project_id);
CREATE INDEX idx_scenes_document_gin ON scenes USING GIN (current_document jsonb_path_ops);
```

### 5.3 scene_events

```sql
CREATE TABLE scene_events (
  id UUID PRIMARY KEY,
  scene_id UUID NOT NULL REFERENCES scenes(id),
  base_revision BIGINT NOT NULL,
  new_revision BIGINT NOT NULL,
  actor_type TEXT NOT NULL CHECK (actor_type IN ('user', 'agent', 'system')),
  actor_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  patch JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_scene_events_scene_revision ON scene_events(scene_id, new_revision DESC);
```

### 5.4 agent_runs

```sql
CREATE TABLE agent_runs (
  id UUID PRIMARY KEY,
  thread_id UUID NOT NULL REFERENCES agent_threads(id),
  project_id UUID NOT NULL REFERENCES projects(id),
  scene_id UUID NOT NULL REFERENCES scenes(id),
  base_scene_revision BIGINT NOT NULL,
  status TEXT NOT NULL CHECK (status IN (
    'queued', 'running', 'waiting_user', 'cancelling',
    'cancelled', 'superseded', 'completed', 'failed'
  )),
  user_message TEXT NOT NULL,
  intent JSONB,
  current_node TEXT,
  interrupt_payload JSONB,
  result JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_runs_thread ON agent_runs(thread_id, created_at DESC);
CREATE INDEX idx_agent_runs_status ON agent_runs(status);
```

### 5.5 agent_events

```sql
CREATE TABLE agent_events (
  id UUID PRIMARY KEY,
  run_id UUID NOT NULL REFERENCES agent_runs(id),
  seq BIGSERIAL,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_events_run_seq ON agent_events(run_id, seq);
```

---

## 6. 后端 API 设计

### 6.1 场景 API

```http
GET    /api/projects/{project_id}/scene
PATCH  /api/projects/{project_id}/scene

# 单个设备实例：场景由设备实例组合而成，这是第一优先级 API
POST   /api/projects/{project_id}/scene/instances
GET    /api/projects/{project_id}/scene/instances/{instance_id}
PATCH  /api/projects/{project_id}/scene/instances/{instance_id}
DELETE /api/projects/{project_id}/scene/instances/{instance_id}

# 流程层连接：对齐前端 Interface 画布 sourceInterface / targetInterface
POST   /api/projects/{project_id}/scene/process-edges
PATCH  /api/projects/{project_id}/scene/process-edges/{edge_id}
DELETE /api/projects/{project_id}/scene/process-edges/{edge_id}

# 物理真实连接：执行/对齐层，通常由后端编译或高级操作生成
POST   /api/projects/{project_id}/scene/physical-edges
DELETE /api/projects/{project_id}/scene/physical-edges/{edge_id}

# 信号连接：第二阶段 UI，可先供 Agent / SimPlan 内部使用
POST   /api/projects/{project_id}/scene/signal-edges
DELETE /api/projects/{project_id}/scene/signal-edges/{edge_id}

GET    /api/projects/{project_id}/scene/events?after_revision=40
```

添加单个设备实例示例：

```json
{
  "base_revision": 42,
  "spec_id": "spec_conveyor_belt_v1",
  "instance_id": "conveyor_3",
  "name": "Conveyor 3",
  "transform": {
    "position": [3.2, 0.0, 1.0],
    "rotation_euler": [0.0, 1.5708, 0.0],
    "scale": [1.0, 1.0, 1.0]
  },
  "params_override": {
    "speed_mps": 0.4
  }
}
```

删除设备实例时，后端必须在同一个 revision patch 中处理关联边：

```json
{
  "base_revision": 42,
  "delete_policy": "delete_incident_edges"
}
```

`delete_policy` 建议支持：

- `reject_if_connected`：如果设备仍有流程/物理/信号连接，拒绝删除。
- `delete_incident_edges`：删除设备并删除所有相关连接，适合用户明确删除设备。
- `stage_for_confirmation`：生成删除预案，返回将受影响的连接，等待用户确认。

创建流程连接示例：

```json
{
  "base_revision": 42,
  "source_instance_id": "conveyor_1",
  "source_interface": "flow_output",
  "target_instance_id": "robot_1",
  "target_interface": "flow_input",
  "edge_type": "material_flow"
}
```

后端校验：

- source / target instance 必须存在。
- `source_interface` 必须存在于 source 设备的 `process_ports`。
- `target_interface` 必须存在于 target 设备的 `process_ports`。
- 第一阶段只允许 `flow_output -> flow_input`。
- 创建后可以同步触发 `compile_process_edges`，生成或更新对应 `physical_edges` 候选。

`PATCH /scene` 请求必须携带 `base_revision`：

```json
{
  "base_revision": 42,
  "patch": [
    { "op": "replace", "path": "/instances/0/params/speed_mps", "value": 0.5 }
  ]
}
```

如果当前 revision 已不是 42，返回：

```json
{
  "error": "SCENE_REVISION_CONFLICT",
  "current_revision": 45,
  "message": "Scene changed after this patch was generated. Reload and rebase before applying."
}
```

### 6.2 拓扑 API

```http
POST /api/projects/{project_id}/interfaces/compile
POST /api/projects/{project_id}/topology/rebuild
GET  /api/projects/{project_id}/topology?scene_revision=latest
POST /api/projects/{project_id}/topology/candidate-edges/{candidate_id}/confirm
POST /api/projects/{project_id}/topology/candidate-edges/{candidate_id}/reject
GET  /api/projects/{project_id}/topology/reachability?from=conveyor_1.exit&to=storage_1.A2
```

`POST /interfaces/compile` 根据当前 `process_edges` 和 `interface_bindings` 生成执行层接口解析结果：

```json
{
  "base_revision": 42,
  "mode": "dry_run"
}
```

返回：

```json
{
  "scene_revision": 42,
  "compiled_physical_edges": [],
  "compiled_signal_edges": [],
  "warnings": [
    {
      "code": "MISSING_BINDING",
      "process_edge_id": "proc_edge_001",
      "message": "robot_1.flow_input 没有绑定到可执行 physical interface"
    }
  ]
}
```

`POST /topology/rebuild` 支持同步或异步：小场景直接返回，大场景返回 task id。

### 6.3 Agent API

```http
POST /api/projects/{project_id}/agent/threads
GET  /api/projects/{project_id}/agent/threads

POST /api/agent/threads/{thread_id}/runs
GET  /api/agent/runs/{run_id}
GET  /api/agent/runs/{run_id}/events
GET  /api/agent/runs/{run_id}/stream        # SSE

POST /api/agent/runs/{run_id}/interrupt
POST /api/agent/runs/{run_id}/resume
POST /api/agent/runs/{run_id}/cancel
POST /api/agent/runs/{run_id}/apply-artifact
```

创建 Agent Run：

```json
{
  "message": "让升降台把传送带出口的箱子送到仓储柜 A2，速度 0.8m/s，然后跑 30 分钟仿真",
  "scene_revision": 42,
  "mode": "plan_and_apply",
  "approval_policy": "require_before_scene_write",
  "attachments": []
}
```

Agent 事件流：

```json
{ "type": "node_started", "node": "intent_router" }
{ "type": "topology_loaded", "topology_id": "topo_42", "warnings": [] }
{ "type": "artifact_created", "artifact_type": "scene_patch", "artifact_id": "art_01" }
{ "type": "interrupt_required", "reason": "ambiguous_target", "questions": [] }
{ "type": "scene_patch_applied", "new_revision": 43 }
{ "type": "done", "result": {} }
```

### 6.4 用户打断与恢复 API

用户在 Agent 运行中追加输入时，不应该简单开启一个无上下文的新对话。应写入 active run 的控制通道。

```http
POST /api/agent/runs/{run_id}/interrupt
```

```json
{
  "kind": "revise",
  "message": "不对，不要用 lift_1，用 lift_2；目标格位改成 B1",
  "strategy": "pause_at_safe_point"
}
```

常见 `kind`：

| kind | 含义 | 处理方式 |
|---|---|---|
| `revise` | 修改需求 | 暂停当前 run，合并新约束，从最近 checkpoint 局部重规划。 |
| `answer` | 回答追问 | 恢复 `waiting_user` 状态的 run。 |
| `approve` | 批准计划或 patch | 执行被挂起的写入/仿真提交。 |
| `pause` | 暂停仿真或长任务 | 通知 worker 暂停，保存 runtime snapshot。 |
| `cancel` | 取消当前 run | 标记 cancelling，停止未提交工具，已提交任务走补偿逻辑。 |
| `query` | 询问当前状态 | 不改变计划，只返回当前 run summary。 |

恢复：

```http
POST /api/agent/runs/{run_id}/resume
```

```json
{
  "resume_type": "clarification_answer",
  "answers": {
    "target_lift": "lift_2",
    "target_cell": "B1"
  }
}
```

### 6.5 仿真 API

```http
POST /api/projects/{project_id}/sim-plans
GET  /api/projects/{project_id}/sim-plans/{plan_id}

POST /api/projects/{project_id}/simulation-runs
GET  /api/projects/{project_id}/simulation-runs/{run_id}
POST /api/simulation-runs/{run_id}/pause
POST /api/simulation-runs/{run_id}/resume
POST /api/simulation-runs/{run_id}/stop
GET  /api/simulation-runs/{run_id}/events
GET  /api/simulation-runs/{run_id}/metrics
```

实时通道：

```http
WS /ws/projects/{project_id}/events
```

事件类型：

- `scene_event`
- `agent_event`
- `simulation_log`
- `simulation_frame`
- `simulation_observation`
- `presence_event`

---

## 7. Agent 设计方案

### 7.1 不采用三阶段 Agent 的原因

不需要把系统拆成“场景理解 Agent / 调度 Agent / 结果 Agent”三个独立智能体。原因：

- 场景理解中大部分工作是确定性图计算，不需要 LLM 自主代理。
- 三个 Agent 会引入不必要的消息传递和责任重叠。
- 用户打断时，最关键的是恢复同一个任务状态，而不是在多个 Agent 之间重新分发上下文。
- 更适合的形态是一个 **Agent Runtime 状态图**，内部包含 LLM 节点和确定性工具节点。

### 7.2 推荐 Agent Runtime

使用 LangGraph，但只把它作为：

- 状态机运行时
- checkpoint / persistence
- human-in-the-loop interrupt / resume
- 条件路由
- 工具调用编排

不要把它用成“LLM 自由决定下一步工具”的纯 ReAct Agent。

### 7.3 AgentState

```python
class AgentState(TypedDict):
    run_id: str
    thread_id: str
    project_id: str
    scene_id: str
    base_scene_revision: int
    user_message: str

    messages: list
    intent: dict | None
    active_constraints: dict

    scene_document: dict | None
    device_specs: dict[str, dict]
    compiled_interfaces: dict | None
    topology_graph: dict | None
    topology_summary: str | None

    task_type: str | None
    slot_resolutions: dict
    candidate_artifacts: list[dict]
    selected_artifact_id: str | None

    validation_errors: list[dict]
    pending_interrupt: dict | None
    user_answers: dict

    scene_patch: list[dict] | None
    sim_plan: dict | None
    simulation_run_id: str | None

    final_response: str | None
```

### 7.4 节点设计

```text
START
  -> load_scene_snapshot
  -> load_device_specs
  -> compile_interfaces
  -> build_or_load_topology
  -> classify_intent
  -> resolve_slots
  -> route_task

route_task:
  scene_query       -> answer_scene_question
  topology_repair   -> propose_topology_edges
  process_config    -> generate_process_patch
  simulation_plan   -> generate_sim_plan
  scene_edit        -> generate_scene_patch

所有生成类节点
  -> validate_artifact
  -> repair_artifact_if_needed      # bounded loop, max 2
  -> maybe_interrupt_for_user
  -> apply_or_stage
  -> emit_result
  -> END

运行中收到 revise / cancel / answer
  -> interrupt_handler
  -> merge_user_update
  -> invalidate_affected_artifacts
  -> route_task 或 resume_previous_node
```

节点顺序的理由：

- `compile_interfaces` 必须在拓扑之前执行，因为流程口需要先映射到真实接口，信号口需要进入 SimPlan 事件空间。
- `resolve_slots` 必须在生成计划前执行，用来消解“这个升降台”“A2”“出口”等自然语言引用，减少 LLM 在规划节点里猜设备 ID。
- `repair_artifact_if_needed` 只处理结构化校验失败后的局部修复，不允许无限循环。
- `maybe_interrupt_for_user` 是业务闸门：歧义、低置信度拓扑、覆盖用户连接、写入场景或启动仿真前都可以暂停。

### 7.5 节点职责

| 节点 | 类型 | 是否调用 LLM | 职责 |
|---|---|---|---|
| `load_scene_snapshot` | 工具节点 | 否 | 读取 scene、base revision、active run、历史 artifacts。 |
| `load_device_specs` | 工具节点 | 否 | 按场景实例加载设备规范，包括真实接口、流程口、信号口、动作模板。 |
| `compile_interfaces` | 工具节点 | 否 | 把前端流程口连接编译到真实接口候选，把信号口映射到事件空间。 |
| `build_or_load_topology` | 工具节点 | 否 | 如果 scene revision 变了，重建拓扑。 |
| `classify_intent` | LLM 结构化输出 | 是 | 判断用户是在查询、修改、规划、仿真、打断还是确认。 |
| `resolve_slots` | LLM + 工具 | 是 | 将“传送带出口”“A2”“左边机器人”等引用解析为 instance/interface/cell id。 |
| `route_task` | 条件路由 | 否 | 根据 intent 进入不同分支。 |
| `generate_scene_patch` | LLM + 工具 | 是 | 生成候选 JSON Patch，不直接写库。 |
| `generate_process_patch` | LLM + 规则 | 是 | 基于设备动作模板生成 process/action 配置。 |
| `generate_sim_plan` | LLM + 规则 | 是 | 生成 SimPlan；轨迹细节只引用算法，不生成低层轨迹点。 |
| `validate_artifact` | 工具节点 | 否 | Schema、参数、拓扑可达性、scene revision、资源冲突校验。 |
| `repair_artifact_if_needed` | 工具 + LLM | 受限 | 根据 validator 错误局部修复，最多 2 次，失败后进入 human-in-the-loop。 |
| `maybe_interrupt_for_user` | 条件节点 | 可选 | 高风险写入、歧义目标、低置信度边时暂停等待用户。 |
| `apply_or_stage` | 工具节点 | 否 | 根据 approval policy 暂存 artifact 或应用 patch / 提交仿真。 |
| `interrupt_handler` | 工具 + LLM | 视情况 | 合并用户中途变更，决定取消、恢复、局部重规划。 |

### 7.6 用户输入类型

| 输入类型 | 示例 | Agent 处理 |
|---|---|---|
| 极简仿真 | “跑一下当前场景” | 读取 topology + 默认 specs，生成 SimPlan，必要时提示悬空端口。 |
| 参数覆盖 | “传送带速度 0.5m/s，跑 10 分钟” | 提取覆盖参数，校验范围，生成 SimPlan。 |
| 工艺目标 | “把传送带出口的箱子送到 A2” | 解析源/目标，查拓扑可达性，生成 process patch 或 SimPlan。 |
| 拓扑修复 | “自动帮我连一下这些设备” | 生成候选边，低置信度要求用户确认。 |
| 设备修改 | “把 lift_1 换成 lift_2” | 生成 scene/process patch，校验 revision。 |
| 运行中打断 | “停一下，目标改成 B1” | 暂停 active run 或 simulation，合并新约束，重规划剩余计划。 |
| 查询诊断 | “为什么不能运行？” | 返回拓扑/参数/资源错误解释，不修改场景。 |

### 7.7 是否需要 Harness / Looping Engineering

结论：**需要 harness，但不需要无界 looping agent**。

这里的 harness 不是另一个 Agent，而是包在 LangGraph 外围和节点之间的工程约束层，负责让 LLM 输出可测试、可中断、可恢复、可审计。

推荐 harness 内容：

| Harness 能力 | 作用 |
|---|---|
| Schema harness | 所有 LLM 输出必须符合 Pydantic schema；不接受自由文本计划。 |
| Tool harness | 每个工具声明输入/输出、超时、幂等性、副作用类型。 |
| Validation harness | Artifact 写库或提交仿真前必须经过确定性 validator。 |
| Revision harness | 所有 scene patch 都绑定 `base_scene_revision`。 |
| Interrupt harness | 每个长节点检查 run status 和 cancellation token，避免旧结果继续写入。 |
| Replay harness | 保存 node event、artifact、validator result，便于复现实验。 |
| Test harness | 用固定场景 fixture 验证拓扑构建、slot resolution、SimPlan 校验。 |

Looping 只保留三类受控循环：

1. **规划修复循环**：`generate -> validate -> repair`，最多 2 次；仍失败就问用户或失败返回。
2. **执行观察循环**：仿真 worker 产生 observation，只有 step 完成、超时、死锁、用户打断时才让 Agent 决策。
3. **人机协商循环**：`proposal -> user revise/approve -> revalidate`，由用户驱动，不让 LLM 自己无限反思。

不建议做：

- 让 LLM 自己反复“想一想再改一改”的无限 self-reflection。
- 让 LLM 在每一帧仿真状态上做决策。
- 把拓扑推断、轨迹生成、资源锁判断交给 LLM 自由发挥。

这个决策的理由：工业仿真系统需要可解释和可复现。真正需要循环的是“状态观测和校验”，不是“LLM 自我思考”。

---

## 8. 用户打断与需求更新机制

### 8.1 Run 状态机

```text
queued
  -> running
  -> waiting_user
  -> running
  -> completed

running
  -> cancelling -> cancelled
running
  -> superseded
running
  -> failed
```

### 8.2 打断处理原则

1. **所有外部副作用必须可追踪**：场景写入、仿真提交、文件生成都要记录 artifact 和 event。
2. **LLM 生成阶段可以被 supersede**：如果用户追加修改，旧结果到达时不再应用。
3. **场景写入前必须检查 revision**：旧 run 基于旧 revision 生成的 patch 不能直接写当前场景。
4. **仿真执行中更新需求要先暂停 worker**：保存 `RuntimeSnapshot`，再决定从当前 world state 重规划还是重启仿真。
5. **打断不是普通聊天消息**：它是对 active run 的控制事件，应进入 `interrupt_handler`。

### 8.3 中途修改需求的处理流程

```text
用户发送 revise
  -> API 写入 agent_events: user_interrupt
  -> active run 标记 pending_interrupt
  -> 如果当前节点可安全暂停：立即 interrupt
  -> 如果当前工具不可中断：等待工具返回，但检查 run 是否 superseded
  -> interrupt_handler 分类用户修改
  -> 合并 active_constraints
  -> 丢弃受影响 artifacts
  -> 从最近 checkpoint 重跑相关分支
  -> 重新 validate
  -> 输出新 proposal 或继续执行
```

### 8.4 修改影响范围判断

| 用户修改 | 影响范围 | 处理 |
|---|---|---|
| 改仿真时长 | SimPlan config | 局部 patch SimPlan，无需重建拓扑。 |
| 改设备速度 | Device params + SimPlan | 校验参数范围，重算相关设备计划。 |
| 改目标格位 | Process + topology reachability | 重新检查目标存在、可达性和容量。 |
| 换设备 | Topology + process + SimPlan | 重新解析相关路径，可能需要重规划。 |
| 移动场景设备 | Scene revision + topology | 重建拓扑，旧计划全部需要 rebase。 |
| 取消任务 | Run / simulation | 停止后续工具和 worker，保留审计事件。 |

### 8.5 Human-in-the-loop 触发条件

必须暂停询问用户：

- 多个设备都符合“升降台”“仓储柜”等自然语言指代。
- 拓扑候选边置信度不足，但计划依赖该边。
- Agent 将要写入场景或覆盖已有人工连接。
- 用户目标与拓扑/设备约束冲突。
- 仿真运行中需要改变已经执行过的动作。

可以自动处理：

- 非关键参数缺失时使用设备规范默认值。
- 用户只改仿真时长、速度倍率等全局参数。
- 高置信度显式连接已经存在且通过校验。

---

## 9. 拓扑构建算法

### 9.1 输入

- `SceneDocument.instances`
- `DeviceSpec.physical_interfaces`
- `DeviceSpec.process_ports`
- `DeviceSpec.signal_ports`
- `DeviceSpec.interface_bindings`
- `SceneDocument.process_edges`
- `SceneDocument.physical_edges`
- `SceneDocument.signal_edges`
- 用户确认/拒绝过的候选边历史

### 9.2 步骤

```text
1. resolve_ports
   对每个 instance 计算端口世界坐标和方向。

2. collect_explicit_edges
   读取 scene.process_edges / physical_edges / signal_edges 中 status=confirmed 的显式连接。
   process_edges 先通过 interface_bindings 编译成候选 physical_edges。

3. build_spatial_index
   对未连接 input/input_output 端口建立 KDTree 或网格索引。

4. infer_candidate_edges
   对每个未连接 material output 物理接口查询附近候选 material input 物理接口。
   过滤条件：端口方向互补、物料类型交集非空、距离阈值、方向夹角阈值。

5. score_candidates
   confidence = distance_score * direction_score * type_score * semantic_score。

6. assemble_graph
   分别构建 process graph、physical graph、signal graph，再生成面向 Agent 的统一 topology view。
   计算弱连通分量、入度出度、拓扑序、环路。

7. emit_warnings
   生成悬空端口、孤立设备、冲突连接、低置信度候选边。
```

### 9.3 自动连接策略

- `confidence >= 0.9`：可作为自动建议，但仍建议第一阶段要求用户确认后写入。
- `0.6 <= confidence < 0.9`：只作为候选边，不自动写入。
- `< 0.6`：不展示给用户，除非诊断模式需要。

### 9.4 Guardian 校验

Agent 生成计划前后都要调用 Guardian：

- 设备是否存在。
- 端口是否存在。
- 目标格位是否存在。
- 源到目标是否可达。
- 参数是否在设备约束范围内。
- 同一资源是否被并发占用。
- 是否依赖未确认候选边。
- 是否基于过期 scene revision。

---

## 10. SimPlan 设计

Agent 不生成底层轨迹点，而是生成结构化 `SimPlan`。

```json
{
  "sim_plan_id": "plan_01",
  "scene_id": "scene_01",
  "base_scene_revision": 43,
  "plan_version": "simplan/v1",
  "goal": "将 conveyor_1.exit 的 box 送到 storage_1.A2，并运行 30 分钟",
  "sim_config": {
    "duration_s": 1800,
    "time_scale": 1.0,
    "random_seed": 42
  },
  "resources": [
    { "resource_id": "material.box.main", "type": "material" },
    { "resource_id": "storage_1.A2", "type": "storage_cell" }
  ],
  "interface_context": {
    "process_path": [
      "conveyor_1.flow_output -> lift_1.flow_input",
      "lift_1.flow_output -> storage_1.flow_input"
    ],
    "physical_path": [
      "conveyor_1.exit -> lift_1.entry",
      "lift_1.output -> storage_1.A2"
    ],
    "signal_bindings": [
      "conveyor_1.part_ready -> lift_1.start",
      "lift_1.done -> storage_1.receive"
    ]
  },
  "actions": [
    {
      "action_id": "a1",
      "device_id": "conveyor_1",
      "action_type": "transport",
      "algorithm": "continuous_transport",
      "params": { "speed_mps": 0.5 },
      "trigger": { "type": "sim_start" },
      "preconditions": [
        { "type": "port_available", "port": "conveyor_1.entry" }
      ],
      "effects": [
        { "type": "material_at", "location": "conveyor_1.exit" }
      ]
    },
    {
      "action_id": "a2",
      "device_id": "lift_1",
      "action_type": "deliver_to_cell",
      "algorithm": "lift_xy_trajectory",
      "params": { "target_cell": "storage_1.A2", "speed_mps": 0.8 },
      "depends_on": ["a1"],
      "trigger": { "type": "signal", "signal": "conveyor_1.part_ready" },
      "preconditions": [
        { "type": "material_at", "location": "conveyor_1.exit" },
        { "type": "cell_empty", "cell": "storage_1.A2" }
      ],
      "effects": [
        { "type": "material_at", "location": "storage_1.A2" },
        { "type": "cell_occupied", "cell": "storage_1.A2" }
      ]
    }
  ]
}
```

---

## 11. 事件与实时通信

### 11.1 REST、SSE、WebSocket 分工

| 通道 | 用途 |
|---|---|
| REST | 创建资源、提交命令、查询快照、打断/恢复 run。 |
| SSE | Agent run 的单向流式输出：节点事件、token、artifact、等待用户、完成。 |
| WebSocket | 场景协同、仿真帧、终端日志、presence、低延迟双向事件。 |

Agent 可以使用 SSE 输出；用户打断通过 REST command 进入。仿真和场景协同使用 WebSocket。

### 11.2 Redis Streams

内部事件建议使用 Redis Streams，而不是只用 Pub/Sub：

- `stream:project:{project_id}:events`
- `stream:agent:{run_id}:events`
- `stream:simulation:{run_id}:frames`

Streams 支持 consumer group、ack、断线后补读，适合 Realtime Hub、审计写入器、指标聚合器分别消费。

---

## 12. 实施路线

### Phase 1：后端事实层与场景 API

- 本地启动 Supabase + Redis，先用 Supabase Storage 保存 GLB 和缩略图。
- 定义 `DeviceSpec`、`SceneDocument`、`SceneEvent`、`ScenePatch` Pydantic schema。
- `DeviceSpec` 必须包含 `physical_interfaces`、`process_ports`、`signal_ports`、`interface_bindings`。
- 建 PostgreSQL 表：projects、assets、device_specs、scenes、scene_events。
- 实现场景 GET/PATCH、单设备实例 add/delete/update、revision conflict。
- 实现 `process_edges` CRUD，对齐前端 `sourceInterface / targetInterface`。
- 前端接入真实保存与加载。

### Phase 2：接口编译与显式拓扑模块

- 实现 `compile_interfaces`：流程口连接 -> 真实接口候选；信号口 -> SimPlan 事件空间。
- 实现真实接口世界坐标计算。
- 实现显式边读取、warnings、拓扑摘要。
- API：rebuild、get topology、confirm/reject candidate。
- 前端先显示显式流程连接和基础异常。

### Phase 2.5：隐式拓扑算法预研

- 在不阻塞主开发的前提下，实现空间邻近 + 端口方向 + 类型兼容的候选边推断原型。
- 先只输出候选和置信度，不自动写入场景。
- 这一阶段对应 `vc_topology_agent_research.md` 第四章，可作为课题算法内容沉淀。

### Phase 3：Agent Runtime MVP

- 建 agent_threads、agent_runs、agent_events、agent_artifacts。
- 实现 LangGraph 状态图：load scene -> load specs -> compile interfaces -> topology -> intent -> slot resolve -> generate artifact -> validate -> stage。
- 加入 harness：schema、tool timeout、revision、interrupt、replay、fixture tests。
- 支持 SSE 事件流。
- 支持 `waiting_user`、`resume answer`、`approve artifact`。

### Phase 4：Scene Patch 与 SimPlan

- Agent 可生成 scene patch / process patch / SimPlan。
- Guardian 校验参数、拓扑可达性、revision。
- 高风险写入走用户确认。
- 应用 patch 后广播 scene event。

### Phase 5：仿真 Worker 与打断重规划

- SimPlan 提交到 worker。
- WebSocket 输出日志、帧、observation。
- 支持 pause/resume/stop。
- 用户运行中 revise：暂停仿真，保存 snapshot，重规划剩余动作。

### Phase 6：审计、回放和优化

- Agent event replay。
- SimPlan 版本管理。
- 仿真结果对比。
- 历史偏好和场景模板复用。
- 后续引入优化 Agent，但仍基于结构化工具和校验。

---

## 13. 推荐目录结构

```text
backend/
  app/
    main.py
    api/
      scenes.py
      topology.py
      agent.py
      simulation.py
      assets.py
    core/
      config.py
      database.py
      redis.py
      security.py
      events.py
    models/
      db/
      schemas/
        scene.py
        device_spec.py
        topology.py
        agent.py
        simplan.py
    services/
      scene_service.py
      topology_service.py
      agent_service.py
      simulation_service.py
      asset_service.py
    topology/
      interface_compiler.py
      port_resolver.py
      graph_builder.py
      inference.py
      validators.py
      summarizer.py
    agent_runtime/
      graph.py
      state.py
      nodes/
        load_context.py
        classify_intent.py
        generate_patch.py
        generate_sim_plan.py
        validate_artifact.py
        interrupt_handler.py
      tools/
        scene_tools.py
        topology_tools.py
        spec_tools.py
        simulation_tools.py
    simulation/
      worker.py
      engine.py
      algorithms/
      telemetry.py
    migrations/
    tests/
```

---

## 14. 关键风险与规避

| 风险 | 规避方式 |
|---|---|
| LLM 生成错误拓扑 | 拓扑由代码生成；LLM 只读摘要。 |
| Agent 覆盖用户场景 | 所有写入基于 revision + patch；高风险写入需确认。 |
| 用户中途改需求导致状态混乱 | 每次执行都有 run_id、checkpoint、status、interrupt event。 |
| 多人协同与 Agent 写入冲突 | scene revision conflict，必要时 rebase 或让用户选择。 |
| 双数据库一致性复杂 | 第一阶段以 PostgreSQL 为主库，Redis/MinIO 只做状态和文件。 |
| 实时帧数据过大 | 高频帧只进 Redis Stream / WebSocket，不长期写 PG。 |
| 仿真运行后再改计划 | pause + RuntimeSnapshot + replan remaining，避免直接改已执行历史。 |
| 流程口和真实接口混乱 | 后端分开保存 `process_edges`、`physical_edges`、`signal_edges`，通过 `interface_bindings` 编译。 |
| 设备类型扩展困难 | 新设备只新增 DeviceSpec 的 interfaces、bindings、actions、algorithm adapter。 |

---

## 15. 官方调研依据

- Visual Components `vcConnector`：连接器属于行为对象，含 `Connection`、`Type`、`connect()`、capacity test 等能力，是设备连接图的核心参考。  
  https://help.visualcomponents.com/4.8/Premium/zh-cn/Python_API/vcConnector.htm
- Visual Components `vcFlow`：流行为暴露 connectors 与容量检查，可类比为后端 port container。  
  https://help.visualcomponents.com/4.8/Premium/zh-cn/Python_API/vcFlow.htm
- Visual Components Connect Interfaces：VC 中接口连接仍需要用户选择、点击或拖线，本系统的隐式拓扑推断是增强能力。  
  https://help.visualcomponents.com/4.8/Premium/en/English/Layout%20Configuration/Connect_Interfaces.htm
- Visual Components `vcTopology`：该类表示几何拓扑，不应与设备拓扑混淆。  
  https://help.visualcomponents.com/4.8/Premium/en/Python_API/vcTopology.htm
- LangGraph interrupt / persistence：用于 Agent 暂停、等待用户输入、checkpoint 和恢复执行。  
  https://docs.langchain.com/oss/python/langgraph/interrupts  
  https://docs.langchain.com/oss/python/langgraph/persistence
- FastAPI WebSocket：用于实时事件、协同和仿真帧推送。  
  https://fastapi.tiangolo.com/advanced/websockets/
- PostgreSQL JSONB：用于保存有固定骨架但字段可扩展的场景、设备规范和 Agent artifact。  
  https://www.postgresql.org/docs/current/datatype-json.html
- Redis Streams：用于内部事件流、consumer group、ack 和断线后补读。  
  https://redis.io/docs/latest/develop/data-types/streams/
