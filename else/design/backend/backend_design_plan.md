# 后端详细技术方案

> 工业三维可视化平台 · Python 后端 · FastAPI + LangGraph + SimPy
> 基于前端方案联调顺序编写

---

## 一、整体架构总览

```
┌──────────────────────────────────────────────────────────────────────┐
│                         客户端（Next.js）                             │
│         REST / SSE / WebSocket                                        │
└──────────────────┬───────────────────────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────────────────────┐
│                      Nginx（反向代理 / 网关）                          │
│  /api/*  → FastAPI:8000                                               │
│  /ws/*   → FastAPI:8000 (WebSocket upgrade)                          │
│  /static/* → MinIO / 直接服务静态资源                                 │
└──────────────────┬───────────────────────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────────────────────┐
│                       FastAPI 主进程（8000）                           │
│                                                                        │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │  Scene      │  │  eCatalog    │  │  Agent       │  │  File     │ │
│  │  Router     │  │  Router      │  │  Router      │  │  Router   │ │
│  └──────┬──────┘  └──────┬───────┘  └──────┬───────┘  └─────┬─────┘ │
│         │                │                  │                │        │
│  ┌──────▼──────────────────────────────────▼───────────────▼──────┐  │
│  │                    Service Layer                                 │  │
│  │  SceneService  CatalogService  AgentService  FileService        │  │
│  └──────┬──────────────┬───────────────┬──────────────┬───────────┘  │
│         │              │               │              │               │
└─────────┼──────────────┼───────────────┼──────────────┼───────────────┘
          │              │               │              │
   ┌──────▼──┐    ┌──────▼──┐    ┌──────▼──┐    ┌──────▼──┐
   │ MongoDB │    │Postgres │    │LangGraph│    │  MinIO  │
   │ (场景)  │    │(目录/权限)│   │+ LLM    │    │(模型文件)│
   └─────────┘    └─────────┘    └─────────┘    └─────────┘
                                        │
                                 ┌──────▼──────┐
                                 │  Redis      │
                                 │ Celery队列  │
                                 │ WS状态      │
                                 └──────┬──────┘
                                        │
                                 ┌──────▼──────┐
                                 │Celery Worker│
                                 │(SimPy仿真)  │
                                 └─────────────┘
```

---

## 二、项目目录结构

```
backend/
├── main.py                        # FastAPI 入口，注册路由、中间件、lifespan
├── config.py                      # 所有配置（env 读取）
├── dependencies.py                # FastAPI 依赖注入（DB session、当前用户）
│
├── api/                           # 路由层（只做请求/响应处理，不含业务逻辑）
│   ├── __init__.py
│   ├── scenes.py                  # 场景 CRUD + WebSocket
│   ├── catalog.py                 # eCatalog 查询 + 模型文件
│   ├── agent.py                   # Agent 会话 + SSE 流式输出
│   ├── simulation.py              # 仿真控制 + 日志 WebSocket
│   ├── files.py                   # 文件上传/下载
│   └── auth.py                    # 认证（JWT）
│
├── services/                      # 业务逻辑层
│   ├── scene_service.py           # 场景增删改查、diff 计算
│   ├── catalog_service.py         # 目录搜索、模型文件服务
│   ├── agent_service.py           # LangGraph 调用、流式包装
│   ├── simulation_service.py      # SimPy 引擎调度
│   └── file_service.py            # MinIO 读写封装
│
├── agents/                        # LangGraph Agent 定义
│   ├── graph.py                   # 主状态机图定义
│   ├── state.py                   # AgentState TypedDict
│   ├── nodes/
│   │   ├── resolver.py            # 意图解析节点
│   │   ├── skill_router.py        # 设备类型路由节点
│   │   ├── device_modeler.py      # 工艺配置生成节点
│   │   ├── scene_patcher.py       # 场景写入节点
│   │   └── guardian.py            # 合法性校验节点
│   └── tools/                     # Agent 可调用工具
│       ├── get_device_spec.py
│       ├── get_scene_context.py
│       ├── validate_config.py
│       └── patch_scene.py
│
├── skills/                        # 设备建模规范 Skill 注册
│   ├── registry.py                # Skill 注册表
│   ├── base.py                    # BaseSkill 抽象类
│   ├── conveyor.py                # 输送带规范
│   ├── robot_arm.py               # 机械臂规范
│   ├── agv.py                     # AGV 规范
│   └── workstation.py             # 工作站规范
│
├── simulation/                    # SimPy 仿真引擎
│   ├── engine.py                  # 主仿真引擎
│   ├── tasks.py                   # Celery 任务定义
│   ├── devices/                   # 各设备仿真模型
│   │   ├── base_device.py
│   │   ├── conveyor_sim.py
│   │   └── robot_sim.py
│   └── reporter.py                # 仿真结果统计
│
├── models/                        # 数据模型
│   ├── pg/                        # SQLAlchemy ORM（PostgreSQL）
│   │   ├── base.py
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── device_catalog.py
│   │   └── device_spec.py
│   └── mongo/                     # Motor ODM（MongoDB）
│       ├── scene.py               # 场景文档 Schema（Pydantic）
│       └── agent_session.py
│
├── schemas/                       # Pydantic 请求/响应 Schema
│   ├── scene.py
│   ├── catalog.py
│   ├── agent.py
│   └── simulation.py
│
├── core/
│   ├── database.py                # PG + Mongo + Redis 连接池
│   ├── minio_client.py            # MinIO 客户端
│   ├── ws_manager.py              # WebSocket 连接管理器
│   ├── auth.py                    # JWT 工具
│   └── exceptions.py             # 自定义异常
│
├── migrations/                    # Alembic 数据库迁移
│   └── versions/
│
├── tests/
│   ├── test_scenes.py
│   ├── test_agent.py
│   └── test_simulation.py
│
├── Dockerfile
├── celery_worker.py               # Celery Worker 入口
├── requirements.txt
└── .env.example
```

---

## 三、技术选型明细

```
Web 框架        FastAPI 0.115           异步优先，原生 SSE/WebSocket 支持
ASGI 服务器     Uvicorn + Gunicorn      多进程部署
ORM（PG）       SQLAlchemy 2.0 async    异步 ORM，统一连接池
ODM（Mongo）    Motor 3.x + Pydantic    异步 MongoDB 驱动
数据校验        Pydantic v2             请求/响应 Schema，速度比 v1 快 5-17x
Agent 框架      LangGraph 0.2           有状态多节点图，支持流式输出
LLM 路由        LiteLLM                 统一接口，可切 GPT-4o / Claude / 本地模型
任务队列        Celery 5.x + Redis      仿真异步计算
仿真引擎        SimPy 4.x               事件驱动离散仿真
对象存储        MinIO Python SDK        GLB/URDF 文件存储
缓存/消息       Redis 7.x (aioredis)    WS 状态、任务结果、eCatalog 缓存
认证            PyJWT + bcrypt          JWT，无状态
迁移            Alembic                 PG schema 版本管理
日志            structlog               结构化日志，适配终端面板输出
```

---

## 四、数据库详细设计

### 4.1 PostgreSQL 完整 Schema

```sql
-- ── 用户 ──────────────────────────────────────────────
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(255) UNIQUE NOT NULL,
    name        VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── 项目 ──────────────────────────────────────────────
CREATE TABLE projects (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scene_doc_id    VARCHAR(36),          -- MongoDB _id（与 project.id 相同）
    thumbnail_key   VARCHAR(500),         -- MinIO 路径
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_projects_owner ON projects(owner_id);

-- ── 项目成员权限 ───────────────────────────────────────
CREATE TABLE project_members (
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role        VARCHAR(20) NOT NULL CHECK (role IN ('OWNER','EDITOR','VIEWER')),
    joined_at   TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (project_id, user_id)
);

-- ── 设备建模规范（每类设备一条）──────────────────────
-- 这是 LLM-Agent Skill 的数据库对应，定义某类设备的工艺参数 Schema
CREATE TABLE device_specs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_category VARCHAR(100) NOT NULL UNIQUE,  -- 'conveyor','robot_arm','agv'...
    spec_version    VARCHAR(20) NOT NULL DEFAULT '1.0',
    skill_name      VARCHAR(100) NOT NULL,          -- 对应 skills/ 目录下的模块名
    -- default_schema：前端"默认"Tab 渲染的参数字段定义
    -- advanced_schema：前端"Advanced"Tab 的参数字段定义
    -- 字段结构见下方 JSON 说明
    default_schema  JSONB NOT NULL DEFAULT '[]',
    advanced_schema JSONB NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- device_specs.default_schema 字段结构示例（JSON）：
-- [
--   {"key": "名称",           "field": "name",             "type": "string"},
--   {"key": "类别",           "field": "category",         "type": "string", "readonly": true},
--   {"key": "ConveyorLength", "field": "conveyor_length",  "type": "number", "unit": "mm",   "default": 1000},
--   {"key": "ConveyorWidth",  "field": "conveyor_width",   "type": "number", "unit": "mm",   "default": 600},
--   {"key": "ConveyorHeight", "field": "conveyor_height",  "type": "number", "unit": "mm",   "default": 800},
--   {"key": "ConveyorSpeed",  "field": "conveyor_speed",   "type": "number", "unit": "mm/s", "default": 200},
--   {"key": "ShowSupport",    "field": "show_support",     "type": "boolean","default": true},
--   {"key": "LiftHome",       "field": "lift_home",        "type": "select", "options": ["Up","Down"], "default": "Down"}
-- ]

-- ── 设备目录（eCatalog）──────────────────────────────
CREATE TABLE device_catalog (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    category        VARCHAR(100) NOT NULL,           -- 关联 device_specs.device_category
    manufacturer    VARCHAR(100),
    model_type      VARCHAR(20) NOT NULL DEFAULT 'glb' CHECK (model_type IN ('glb','urdf')),
    model_file_key  VARCHAR(500) NOT NULL,           -- MinIO: models/{id}.glb
    thumbnail_key   VARCHAR(500),                    -- MinIO: thumbnails/{id}.jpg
    -- 设备基础规格（不随实例变化的物理参数，只读展示用）
    base_metadata   JSONB DEFAULT '{}',
    -- 搜索用字段（冗余存储，避免 JSONB 全表扫）
    tags            TEXT[] DEFAULT '{}',
    is_public       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_catalog_category ON device_catalog(category);
CREATE INDEX idx_catalog_tags ON device_catalog USING GIN(tags);
CREATE INDEX idx_catalog_name ON device_catalog USING GIN(to_tsvector('english', name));

-- ── Agent 会话（元数据，消息存 MongoDB）─────────────
CREATE TABLE agent_sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id),
    title       VARCHAR(255),
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
```

---

### 4.2 MongoDB 文档结构

#### 场景文档（Collection: `scenes`）

```python
# models/mongo/scene.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class Transform(BaseModel):
    position: list[float] = [0.0, 0.0, 0.0]   # [x, y, z] 米
    rotation: list[float] = [0.0, 0.0, 0.0]   # Euler rad [rx, ry, rz]
    scale:    list[float] = [1.0, 1.0, 1.0]

class Behavior(BaseModel):
    type: str                          # 'pick_and_place' | 'transport' | 'process'
    params: dict = {}                  # 由 device_spec.default_schema 约束的参数

class ProcessConfig(BaseModel):
    skill_version: str = "1.0"
    behaviors: list[Behavior] = []
    states: list[str] = ["idle", "running", "error"]
    signals: dict = {"input": [], "output": []}

class DeviceInstance(BaseModel):
    instance_id: str                   # 场景内唯一，前端 crypto.randomUUID()
    catalog_id: str                    # 关联 PG device_catalog.id
    name: str
    category: str                      # 冗余存储，避免 JOIN
    transform: Transform = Transform()
    process_config: ProcessConfig = ProcessConfig()
    # 属性面板"默认"Tab 中用户可编辑的参数值
    # 字段由 device_specs.default_schema 定义，值在这里存储
    default_params: dict = {}
    # 属性面板"Advanced"Tab 参数值
    advanced_params: dict = {}
    visible: bool = True
    locked: bool = False

class Connection(BaseModel):
    id: str
    from_device: str                   # instance_id
    to_device: str
    type: str = "material_flow"        # 'material_flow' | 'signal' | 'path'
    properties: dict = {}

class FloorConfig(BaseModel):
    width: float = 50.0                # 米
    depth: float = 30.0
    grid_size: float = 1.0

class SimulationConfig(BaseModel):
    duration: float = 3600.0          # 秒
    warm_up: float = 0.0
    random_seed: int = 42
    speed_multiplier: float = 1.0

class SceneDocument(BaseModel):
    id: str                            # = project.id（与 PG 同步）
    version: int = 0                   # 乐观锁，每次写入 +1
    name: str
    floor: FloorConfig = FloorConfig()
    devices: list[DeviceInstance] = []
    connections: list[Connection] = []
    simulation_config: SimulationConfig = SimulationConfig()
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

#### Agent 会话消息（Collection: `agent_messages`）

```python
class AgentMessage(BaseModel):
    id: str
    session_id: str
    role: str                          # 'user' | 'assistant'
    content: str                       # 完整文本（流结束后再写入）
    # Agent 生成的结构化结果（如果有）
    patch_applied: Optional[dict] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

---

### 4.3 Redis 数据结构

```
# WebSocket 连接管理
ws:connections:{project_id}         → Set<user_id>          在线用户

# 场景实时状态（仿真运行时）
sim:state:{project_id}              → Hash
    running         "true"/"false"
    sim_time        "3600.5"
    speed           "1.0"
    started_at      "2026-04-15T..."

# 仿真帧数据（前端动画驱动）
sim:frames:{project_id}             → Stream（Redis Streams）
    device_id, state, position, joints...

# eCatalog 搜索缓存
catalog:search:{hash(query)}        → String (JSON)          TTL: 300s

# Agent 流式 token 临时缓冲
agent:stream:{session_id}           → List<token>            TTL: 600s

# Celery 任务状态
celery-task-meta-{task_id}          → String (自动管理)
```

---

## 五、API 接口设计

### 5.1 认证

```
POST   /api/auth/oauth/exchange    OAuth 资料换发系统 access token / refresh token
POST   /api/auth/register          注册
POST   /api/auth/login             登录，返回 JWT
POST   /api/auth/refresh           刷新 Token
GET    /api/auth/me                当前用户信息
```

### 5.2 项目管理

```
GET    /api/projects               列出我的项目
POST   /api/projects               新建项目（同时创建 MongoDB 场景文档）
GET    /api/projects/{id}          项目详情
PUT    /api/projects/{id}          更新项目元数据
DELETE /api/projects/{id}          删除项目

GET    /api/projects/{id}/members              成员列表
POST   /api/projects/{id}/members             邀请成员
PATCH  /api/projects/{id}/members/{user_id}   修改权限
DELETE /api/projects/{id}/members/{user_id}   移除成员
```

### 5.3 场景管理

```
GET    /api/projects/{id}/scene
       → 返回完整 SceneDocument JSON

PATCH  /api/projects/{id}/scene
       Body: JSON Patch 数组（RFC 6902）
       → 原子更新，version+1，广播 WebSocket diff

POST   /api/projects/{id}/scene/devices
       Body: { catalog_id, transform }
       → 添加设备实例，返回 instance_id

PATCH  /api/projects/{id}/scene/devices/{instance_id}
       Body: { transform?, default_params?, advanced_params?, process_config? }
       → 更新设备，广播变更

DELETE /api/projects/{id}/scene/devices/{instance_id}
       → 删除设备

POST   /api/projects/{id}/scene/connections
       Body: { from_device, to_device, type }
       → 添加连接

DELETE /api/projects/{id}/scene/connections/{conn_id}

# WebSocket：场景实时同步
WS     /ws/scenes/{project_id}?token={jwt}

# WS 消息格式（服务端 → 客户端）：
# { "type": "device_added",    "payload": DeviceInstance }
# { "type": "device_updated",  "payload": { instance_id, changes } }
# { "type": "device_deleted",  "payload": { instance_id } }
# { "type": "connection_added","payload": Connection }
# { "type": "user_joined",     "payload": { user_id, name } }
# { "type": "user_left",       "payload": { user_id } }
```

### 5.4 eCatalog

```
GET    /api/catalog
       QueryParams: category, manufacturer, q(关键词), page, page_size
       → 分页设备列表（含缩略图 URL）

GET    /api/catalog/{id}
       → 设备详情（含 default_schema、advanced_schema）

GET    /api/catalog/{id}/model
       → 302 重定向到 MinIO 预签名 URL（GLB/URDF 文件）

GET    /api/catalog/categories
       → 所有类别列表（供目录树渲染）

GET    /api/catalog/manufacturers
       → 所有制造商列表

POST   /api/catalog                        [管理员]
       → 上传新设备（元数据 + 文件）

GET    /api/device-specs/{category}
       → 返回该类别的 default_schema + advanced_schema
       → 前端属性面板据此动态渲染表单
```

### 5.5 Agent 工艺建模

```
POST   /api/agent/sessions
       Body: { project_id }
       → 创建会话，返回 session_id

GET    /api/agent/sessions/{id}/messages
       → 历史消息列表

POST   /api/agent/sessions/{id}/messages
       Body: { content: "让机械臂以8秒节拍..." }
       → SSE 流式响应（text/event-stream）

# SSE 事件格式：
# data: {"type": "token",  "data": "根"}            ← 打字机 token
# data: {"type": "token",  "data": "据"}
# data: {"type": "patch",  "data": {...scene_patch}} ← 场景变更（可选）
# data: {"type": "done",   "data": null}             ← 结束
# data: {"type": "error",  "data": "错误信息"}       ← 出错

DELETE /api/agent/sessions/{id}
       → 删除会话
```

### 5.6 仿真

```
POST   /api/projects/{id}/simulation/start
       Body: { speed_multiplier: 1.0 }
       → 提交 Celery 任务，返回 task_id

POST   /api/projects/{id}/simulation/pause
POST   /api/projects/{id}/simulation/resume
POST   /api/projects/{id}/simulation/stop

GET    /api/projects/{id}/simulation/status
       → { running, sim_time, task_id, progress }

GET    /api/projects/{id}/simulation/stats
       → OEE、节拍、瓶颈分析等统计结果

# WebSocket：终端日志 + 仿真帧数据
WS     /ws/simulation/{project_id}?token={jwt}

# WS 消息格式：
# { "type": "log",    "level": "info", "text": "\x1b[32m[SimPy]\x1b[0m ..." }
# { "type": "frame",  "sim_time": 1.5, "devices": [{ instance_id, state, joints }] }
# { "type": "done",   "stats": { ... } }
```

### 5.7 文件服务

```
POST   /api/files/upload
       Multipart: file (GLB/GLTF/URDF/STEP)
       → 上传到 MinIO，返回 file_key

GET    /api/files/{key}/presigned
       → 返回 MinIO 预签名下载 URL（有效期 1h）

POST   /api/projects/{id}/export/layout
       → 导出场景为 JSON 文件

POST   /api/projects/{id}/export/bom
       → 导出 BOM 报表（CSV）
```

---

## 六、LangGraph Agent 详细设计

### 6.1 状态定义

```python
# agents/state.py
from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # 输入
    session_id: str
    project_id: str
    user_message: str

    # 中间状态
    messages: Annotated[list, add_messages]   # LangGraph 消息历史
    intent: Optional[dict]                    # Resolver 解析结果
    target_instances: list[str]               # 目标设备 instance_id 列表
    device_category: Optional[str]            # Skill Router 确定的类别
    scene_context: Optional[dict]             # 相邻设备信息

    # 输出
    generated_config: Optional[dict]          # Device Modeler 生成的 process_config
    scene_patches: list[dict]                 # 待写入的 JSON Patch 列表
    validation_errors: list[str]              # Guardian 发现的问题
    final_response: str                       # 返回给用户的自然语言说明
```

### 6.2 节点实现

```python
# agents/nodes/resolver.py
from langchain_core.messages import HumanMessage, SystemMessage
from agents.state import AgentState

RESOLVER_PROMPT = """
你是一个工业车间布局助手。分析用户的请求，提取：
1. 操作类型：configure_device | add_device | connect_devices | query
2. 目标设备：设备名称或 instance_id
3. 工艺意图：用户想实现的工艺行为描述

以 JSON 格式返回，不要有任何其他文字。
"""

async def resolver_node(state: AgentState) -> dict:
    llm = get_llm()  # LiteLLM 封装
    response = await llm.ainvoke([
        SystemMessage(content=RESOLVER_PROMPT),
        HumanMessage(content=state["user_message"]),
    ])
    intent = json.loads(response.content)
    return {"intent": intent}


# agents/nodes/skill_router.py
from skills.registry import SkillRegistry

async def skill_router_node(state: AgentState) -> dict:
    intent = state["intent"]
    # 从场景中获取目标设备的 category
    scene = await get_scene(state["project_id"])
    target = next(
        (d for d in scene["devices"] if d["name"] in intent.get("target_devices", [])),
        None
    )
    category = target["category"] if target else intent.get("inferred_category")
    # 验证 Skill 注册表中有对应规范
    skill = SkillRegistry.get(category)
    return {
        "device_category": category,
        "target_instances": [target["instance_id"]] if target else [],
    }


# agents/nodes/device_modeler.py
async def device_modeler_node(state: AgentState) -> dict:
    spec = await get_device_spec(state["device_category"])  # 从 PG 查规范
    skill = SkillRegistry.get(state["device_category"])

    # 构造 Prompt：将规范 Schema 注入，要求 LLM 生成合规配置
    prompt = skill.build_prompt(
        intent=state["intent"],
        spec_schema=spec["default_schema"],
        scene_context=state["scene_context"],
    )
    llm = get_llm()
    # 强制 JSON 输出（Structured Output）
    structured_llm = llm.with_structured_output(skill.output_schema)
    config = await structured_llm.ainvoke(prompt)

    return {"generated_config": config.model_dump()}


# agents/nodes/scene_patcher.py
async def scene_patcher_node(state: AgentState) -> dict:
    patches = []
    for instance_id in state["target_instances"]:
        patches.append({
            "op": "replace",
            "path": f"/devices/{find_device_index(instance_id)}/process_config",
            "value": state["generated_config"],
        })
    # 写入 MongoDB
    await apply_patches(state["project_id"], patches)
    # 广播 WebSocket
    await ws_manager.broadcast(state["project_id"], {
        "type": "process_config_updated",
        "payload": {
            "instance_id": state["target_instances"][0],
            "config": state["generated_config"],
        }
    })
    return {"scene_patches": patches}


# agents/nodes/guardian.py
async def guardian_node(state: AgentState) -> dict:
    errors = []
    config = state["generated_config"]
    spec = await get_device_spec(state["device_category"])

    # 1. JSON Schema 校验
    try:
        jsonschema.validate(config, spec["validation_schema"])
    except jsonschema.ValidationError as e:
        errors.append(f"参数校验失败：{e.message}")

    # 2. 业务规则校验（如机械臂 payload 不能超过额定值）
    skill = SkillRegistry.get(state["device_category"])
    business_errors = skill.validate_business_rules(config, state["scene_context"])
    errors.extend(business_errors)

    return {"validation_errors": errors}
```

### 6.3 图结构与条件路由

```python
# agents/graph.py
from langgraph.graph import StateGraph, END
from agents.state import AgentState

def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("resolver",       resolver_node)
    graph.add_node("skill_router",   skill_router_node)
    graph.add_node("device_modeler", device_modeler_node)
    graph.add_node("guardian",       guardian_node)
    graph.add_node("scene_patcher",  scene_patcher_node)

    graph.set_entry_point("resolver")
    graph.add_edge("resolver",       "skill_router")
    graph.add_edge("skill_router",   "device_modeler")
    graph.add_edge("device_modeler", "guardian")

    # Guardian 校验失败 → 回到 device_modeler 重试（最多 3 次）
    graph.add_conditional_edges(
        "guardian",
        route_after_guardian,
        {
            "patch":  "scene_patcher",  # 校验通过
            "retry":  "device_modeler", # 校验失败，重试
            "abort":  END,              # 超过重试次数
        }
    )
    graph.add_edge("scene_patcher", END)

    return graph.compile()

def route_after_guardian(state: AgentState) -> str:
    if not state["validation_errors"]:
        return "patch"
    retry_count = state.get("retry_count", 0)
    if retry_count < 3:
        return "retry"
    return "abort"
```

### 6.4 SSE 流式输出包装

```python
# api/agent.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from agents.graph import build_graph

router = APIRouter(prefix="/api/agent")
graph = build_graph()

@router.post("/sessions/{session_id}/messages")
async def send_message(session_id: str, body: MessageRequest, user=Depends(get_current_user)):

    async def event_stream():
        async for event in graph.astream_events(
            input={
                "session_id": session_id,
                "project_id": body.project_id,
                "user_message": body.content,
            },
            version="v2",
        ):
            kind = event["event"]

            # LLM 生成 token → 转发给前端打字机
            if kind == "on_chat_model_stream":
                token = event["data"]["chunk"].content
                if token:
                    yield f"data: {json.dumps({'type':'token','data':token})}\n\n"

            # 场景 Patch 完成 → 通知前端刷新
            elif kind == "on_chain_end" and event["name"] == "scene_patcher":
                patches = event["data"]["output"]["scene_patches"]
                yield f"data: {json.dumps({'type':'patch','data':patches})}\n\n"

            # Guardian 发现错误
            elif kind == "on_chain_end" and event["name"] == "guardian":
                errors = event["data"]["output"]["validation_errors"]
                if errors:
                    yield f"data: {json.dumps({'type':'warning','data':errors})}\n\n"

        yield f"data: {json.dumps({'type':'done','data':None})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

---

## 七、Skill 规范系统设计

```python
# skills/base.py
from abc import ABC, abstractmethod
from pydantic import BaseModel

class BaseSkill(ABC):
    category: str          # 'conveyor' | 'robot_arm' | 'agv' ...
    version: str = "1.0"

    @abstractmethod
    def build_prompt(self, intent: dict, spec_schema: list, scene_context: dict) -> str:
        """构造发给 LLM 的 Prompt，将规范约束注入"""
        ...

    @abstractmethod
    def validate_business_rules(self, config: dict, scene_context: dict) -> list[str]:
        """业务规则校验（Schema 校验之外的逻辑）"""
        ...

    @property
    @abstractmethod
    def output_schema(self) -> type[BaseModel]:
        """LLM 结构化输出的 Pydantic Schema"""
        ...


# skills/conveyor.py
class ConveyorSkill(BaseSkill):
    category = "conveyor"

    class OutputSchema(BaseModel):
        conveyor_speed: float      # mm/s，范围 50-2000
        conveyor_length: float     # mm
        accumulate: bool = True
        lift_delay: float = 2.0   # s

    def build_prompt(self, intent, spec_schema, scene_context):
        return f"""
你是传送带工艺配置专家。根据以下信息生成传送带的工艺参数：

用户需求：{intent['description']}
相邻设备：{json.dumps(scene_context, ensure_ascii=False)}
参数约束：{json.dumps(spec_schema, ensure_ascii=False)}

规则：
- conveyor_speed 必须在 50-2000 mm/s 之间
- 如果上游是机械臂，建议速度设为机械臂节拍时间匹配值
- accumulate 用于设备间缓冲，有机械臂时建议开启

以 JSON 格式输出，不要有其他文字。
"""

    def validate_business_rules(self, config, scene_context):
        errors = []
        if not (50 <= config["conveyor_speed"] <= 2000):
            errors.append(f"速度 {config['conveyor_speed']} 超出范围 [50, 2000] mm/s")
        return errors

    @property
    def output_schema(self):
        return self.OutputSchema


# skills/registry.py
class SkillRegistry:
    _registry: dict[str, BaseSkill] = {}

    @classmethod
    def register(cls, skill: BaseSkill):
        cls._registry[skill.category] = skill

    @classmethod
    def get(cls, category: str) -> BaseSkill:
        if category not in cls._registry:
            raise ValueError(f"未找到设备类别 '{category}' 的建模规范")
        return cls._registry[category]

# 注册所有 Skill
SkillRegistry.register(ConveyorSkill())
SkillRegistry.register(RobotArmSkill())
SkillRegistry.register(AGVSkill())
```

---

## 八、仿真引擎设计（SimPy）

```python
# simulation/engine.py
import simpy
import asyncio
from simulation.reporter import SimReporter

class WorkshopSimulation:
    def __init__(self, scene: dict, ws_callback):
        self.scene = scene
        self.ws_callback = ws_callback       # 发送帧数据的 WebSocket 回调
        self.env = simpy.Environment()
        self.reporter = SimReporter()
        self.device_processes = {}

    def build(self):
        """根据 scene.devices 构建仿真模型"""
        for device in self.scene["devices"]:
            category = device["category"]
            config = device["process_config"]

            if category == "conveyor":
                proc = ConveyorSim(self.env, device, config, self.reporter)
            elif category == "robot_arm":
                proc = RobotSim(self.env, device, config, self.reporter)
            elif category == "agv":
                proc = AGVSim(self.env, device, config, self.reporter)

            self.device_processes[device["instance_id"]] = proc

        # 建立设备间连接（Connection → SimPy 资源共享）
        for conn in self.scene["connections"]:
            self._connect(conn)

    def _connect(self, conn: dict):
        src = self.device_processes[conn["from_device"]]
        dst = self.device_processes[conn["to_device"]]
        src.output = dst.input_buffer     # SimPy Container/Store

    async def run(self, duration: float, speed: float = 1.0):
        self.build()
        # 每隔 0.1 仿真秒推送一帧
        frame_interval = 0.1

        while self.env.now < duration:
            self.env.run(until=self.env.now + frame_interval)

            # 收集当前帧各设备状态
            frame = {
                "sim_time": self.env.now,
                "devices": [
                    {
                        "instance_id": iid,
                        "state": proc.current_state,
                        "metrics": proc.get_metrics(),
                    }
                    for iid, proc in self.device_processes.items()
                ],
            }
            # 通过 WebSocket 推送到前端终端
            await self.ws_callback({
                "type": "frame",
                **frame
            })
            # 按速度倍率控制真实时间
            await asyncio.sleep(frame_interval / speed)

        return self.reporter.summarize()


# simulation/tasks.py（Celery 任务）
from celery import Celery
from celery.utils.log import get_task_logger

celery = Celery("simulation", broker="redis://localhost:6379/1")
logger = get_task_logger(__name__)

@celery.task(bind=True)
def run_simulation_task(self, project_id: str, scene: dict, config: dict):
    """在 Celery Worker 中运行仿真（CPU 密集，不占用主进程）"""
    import asyncio
    from simulation.engine import WorkshopSimulation

    # Worker 中通过 Redis Pub/Sub 发送帧数据
    def ws_callback_sync(frame):
        redis_client.publish(f"sim:frames:{project_id}", json.dumps(frame))

    sim = WorkshopSimulation(scene, ws_callback_sync)
    result = asyncio.run(sim.run(
        duration=config["duration"],
        speed=config["speed_multiplier"],
    ))
    return result
```

---

## 九、WebSocket 连接管理器

```python
# core/ws_manager.py
from fastapi import WebSocket
from collections import defaultdict
import json

class ConnectionManager:
    def __init__(self):
        # project_id → {user_id: WebSocket}
        self._connections: dict[str, dict[str, WebSocket]] = defaultdict(dict)

    async def connect(self, project_id: str, user_id: str, ws: WebSocket):
        await ws.accept()
        self._connections[project_id][user_id] = ws
        # 通知其他人
        await self.broadcast(project_id, {
            "type": "user_joined",
            "payload": {"user_id": user_id}
        }, exclude=user_id)

    async def disconnect(self, project_id: str, user_id: str):
        self._connections[project_id].pop(user_id, None)
        await self.broadcast(project_id, {
            "type": "user_left",
            "payload": {"user_id": user_id}
        })

    async def broadcast(self, project_id: str, message: dict, exclude: str = None):
        """向项目内所有在线用户广播消息"""
        dead = []
        for uid, ws in self._connections[project_id].items():
            if uid == exclude:
                continue
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                dead.append(uid)
        for uid in dead:
            self._connections[project_id].pop(uid, None)

    async def send_to(self, project_id: str, user_id: str, message: dict):
        ws = self._connections[project_id].get(user_id)
        if ws:
            await ws.send_text(json.dumps(message))

ws_manager = ConnectionManager()  # 全局单例
```

---

## 十、依赖注入与中间件

```python
# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化连接池
    await database.connect_all()       # PG + Mongo + Redis
    await minio_client.ensure_buckets()
    yield
    # 关闭时清理
    await database.disconnect_all()

app = FastAPI(title="3D Workshop Platform", lifespan=lifespan)

app.add_middleware(CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(scenes_router)
app.include_router(catalog_router)
app.include_router(agent_router)
app.include_router(simulation_router)
app.include_router(files_router)


# dependencies.py
from fastapi import Depends, HTTPException
from core.auth import decode_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = decode_jwt(token)
    user = await UserRepository.get(payload["sub"])
    if not user:
        raise HTTPException(401, "用户不存在")
    return user

async def require_editor(project_id: str, user=Depends(get_current_user)):
    member = await ProjectRepository.get_member(project_id, user.id)
    if not member or member.role == "VIEWER":
        raise HTTPException(403, "需要编辑权限")
    return user
```

---

## 十一、requirements.txt

```
# Web 框架
fastapi==0.115.0
uvicorn[standard]==0.30.0
python-multipart==0.0.9

# 数据库
sqlalchemy[asyncio]==2.0.35
asyncpg==0.29.0              # PG 异步驱动
motor==3.5.0                  # MongoDB 异步驱动
redis[hiredis]==5.0.8         # Redis 异步客户端
alembic==1.13.0

# 数据校验
pydantic==2.9.0
pydantic-settings==2.5.0

# Agent / LLM
langgraph==0.2.35
langchain-core==0.3.15
litellm==1.50.0
jsonschema==4.23.0

# 任务队列 / 仿真
celery==5.4.0
simpy==4.1.1

# 文件存储
minio==7.2.9

# 认证
pyjwt==2.9.0
bcrypt==4.2.0
python-jose==3.3.0

# 日志
structlog==24.4.0

# 工具
httpx==0.27.0                 # 内部 HTTP 调用
orjson==3.10.7                # 高性能 JSON
python-dotenv==1.0.1
```

---

## 十二、开发优先级（与前端联调顺序对齐）

```
Week 1-2   数据库初始化 + 认证接口
           Alembic 迁移脚本（所有 PG 表）
           MongoDB 连接 + SceneDocument 初始化
           JWT 登录/注册

Week 3-4   eCatalog 接口 + MinIO 集成
           设备目录 CRUD + 模型文件上传
           device_specs 表初始数据（输送带/机械臂）
           前端联调：eCatalog 树形目录 + 模型文件加载

Week 5-6   场景管理接口 + WebSocket
           场景 CRUD + JSON Patch 应用
           WebSocket 连接管理器
           前端联调：拖拽入场持久化 + 属性面板读写

Week 7-8   LangGraph Agent 骨架
           Resolver + Skill Router 节点
           ConveyorSkill + RobotArmSkill 实现
           SSE 流式输出接口
           前端联调：AI 聊天打字机效果

Week 9-10  SimPy 仿真引擎
           设备仿真模型（Conveyor + Robot）
           Celery 任务 + Redis Pub/Sub
           WebSocket 帧数据推送
           前端联调：终端日志 + 仿真控制条
```
