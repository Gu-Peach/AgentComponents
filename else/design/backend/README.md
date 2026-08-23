# 后端架构设计

> FastAPI + LangGraph + SimPy
> Python 异步优先 · 调度与执行分离

---

## 📋 目录结构

```
backend/
├── main.py                        # FastAPI 入口，注册路由、中间件、lifespan
├── config.py                      # 环境变量配置
├── dependencies.py                # FastAPI 依赖注入
│
├── api/                           # 路由层（请求/响应处理）
│   ├── auth.py                    # 认证（JWT）
│   ├── scenes.py                  # 场景 CRUD + WebSocket
│   ├── catalog.py                 # eCatalog 查询 + 模型文件
│   ├── agent.py                   # Agent 会话 + SSE 流式输出
│   ├── simulation.py              # 仿真控制 + 日志 WebSocket
│   └── files.py                   # 文件上传/下载
│
├── services/                      # 业务逻辑层
│   ├── scene_service.py           # 场景增删改查、diff 计算
│   ├── catalog_service.py         # 目录搜索、模型文件服务
│   ├── layout_service.py          # 布局实例化（instantiate_layout）
│   ├── agent_service.py           # LangGraph 调用、流式包装
│   ├── simulation_service.py      # SimPy 引擎调度
│   └── file_service.py            # MinIO 读写封装
│
├── agents/                        # LangGraph Agent 定义
│   └── simulation/
│       ├── graph.py               # 主状态机图定义
│       ├── state.py               # SimAgentState TypedDict
│       ├── nodes/
│       │   ├── orchestrator.py    # ReAct 主节点
│       │   ├── plan_generator.py  # 计划生成节点
│       │   ├── plan_validator.py  # 计划校验节点
│       │   ├── executor.py        # 执行节点
│       │   └── clarifier.py       # Human-in-loop 中断节点
│       └── skills/
│           ├── read_scene_config.py
│           ├── analyze_topology.py
│           ├── select_device_algorithm.py
│           ├── resolve_device_params.py
│           └── generate_coordination_rules.py
│
├── simulation/                    # SimPy 仿真引擎
│   ├── engine.py                  # WorkshopSimulation（SimPy）
│   ├── tasks.py                   # Celery 任务定义
│   ├── algorithms/
│   │   ├── conveyor.py            # continuous_transport
│   │   ├── lift.py                # lift_xy_trajectory
│   │   └── storage.py             # cell_allocation_fifo
│   └── reporter.py                # 仿真结果统计
│
├── models/                        # 数据模型
│   ├── pg/                        # SQLAlchemy ORM（PostgreSQL）
│   │   ├── base.py
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── device_catalog.py
│   │   └── layout_catalog.py
│   └── mongo/                     # Pydantic 文档模型（MongoDB）
│       ├── scene.py               # SceneDocument
│       ├── device_spec.py
│       ├── layout_template.py
│       └── agent_message.py
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
│   └── exceptions.py              # 自定义异常
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

## 🏗️ 系统架构

```
客户端（Next.js）
    │  REST / SSE / WebSocket
    ▼
Nginx（反向代理 / WebSocket upgrade）
    │  /api/* → FastAPI:8000
    │  /ws/*  → FastAPI:8000
    ▼
FastAPI 主进程（8000）
    ├── Scene Router      → SceneService      → MongoDB (scenes)
    ├── Catalog Router    → CatalogService    → PostgreSQL + MinIO
    ├── Agent Router      → AgentService      → LangGraph + LLM
    ├── Simulation Router → SimulationService → Celery + SimPy
    └── Files Router      → FileService       → MinIO
                                    │
                              Redis（实时状态 / 任务队列）
                                    │
                             Celery Worker（SimPy 仿真）
```

---

## 🔧 核心技术实现

### 1. AI 调度层与执行层分离

```
用户输入（自然语言）
    │
    ▼
AI 调度层（LangGraph Agent）
    理解意图 → 解析场景 → 生成 SimPlan JSON
    │
    │ SimPlan JSON（两层之间的唯一接口）
    ▼
执行层（SimPy + 轨迹算法）
    ConveyorProcess  → continuous_transport 算法
    LiftProcess      → lift_xy_trajectory 算法
    StorageProcess   → cell_allocation_fifo 算法
    │
    ├── 帧数据 → WebSocket → 3D 动画
    └── 日志   → WebSocket → Terminal Panel
```

### 2. 布局实例化逻辑

从布局模板生成场景实例的核心服务：

- 解析 `configFile` 引用（catalog: / file:）
- 合并默认参数 + 布局覆盖参数
- 从拓扑生成连接关系
- 写入 MongoDB scenes 集合

### 3. WebSocket 连接管理

实时多人协同编辑的核心：

- 维护 project_id → {user_id: WebSocket} 映射
- 场景修改自动广播给所有在线用户
- 支持用户加入/离开通知

---

## 📡 完整 API 接口

### 认证
```
POST /api/auth/register
POST /api/auth/login        → 返回 JWT
POST /api/auth/refresh
GET  /api/auth/me
```

### 项目管理
```
GET    /api/projects
POST   /api/projects
GET    /api/projects/{id}
PUT    /api/projects/{id}
DELETE /api/projects/{id}
```

### 场景管理
```
GET    /api/projects/{id}/scene
PATCH  /api/projects/{id}/scene
POST   /api/projects/{id}/scene/devices
PATCH  /api/projects/{id}/scene/devices/{instance_id}
DELETE /api/projects/{id}/scene/devices/{instance_id}
POST   /api/projects/{id}/scene/load-layout

WS /ws/scenes/{project_id}?token={jwt}
```

### eCatalog
```
GET /api/catalog?category=&manufacturer=&q=&page=
GET /api/catalog/{id}
GET /api/catalog/{id}/model              → MinIO 预签名 URL
GET /api/catalog/categories
GET /api/device-specs/{category}
GET /api/layouts
GET /api/layouts/{id}
```

### Agent 仿真
```
POST /api/agent/sessions
GET  /api/agent/sessions/{id}/messages
POST /api/agent/sessions/{id}/messages   → SSE 流式响应
DELETE /api/agent/sessions/{id}
```

### 仿真控制
```
POST /api/projects/{id}/simulation/start
POST /api/projects/{id}/simulation/pause
POST /api/projects/{id}/simulation/resume
POST /api/projects/{id}/simulation/stop
GET  /api/projects/{id}/simulation/status
GET  /api/projects/{id}/simulation/stats

WS /ws/simulation/{project_id}?token={jwt}
```

---

## 📦 核心依赖

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy[asyncio]==2.0.35
asyncpg==0.29.0
motor==3.5.0
redis[hiredis]==5.0.8
alembic==1.13.0
pydantic==2.9.0
langgraph==0.2.35
langchain-core==0.3.15
litellm==1.50.0
celery==5.4.0
simpy==4.1.1
minio==7.2.9
pyjwt==2.9.0
structlog==24.4.0
```

---

## 🚀 开发顺序

### Week 9: 认证 + 项目管理
- JWT 登录注册
- 项目 CRUD + 成员权限

### Week 10: 场景管理 API
- 场景 CRUD + JSON Patch
- Connection CRUD

### Week 11: WebSocket 场景同步
- ConnectionManager
- 场景修改自动广播

### Week 12: 布局加载 + 文件服务
- instantiate_layout 服务
- 文件上传/下载/导出

### Week 13: eCatalog 完整 API
- 分页搜索（Redis 缓存）
- 布局目录接口

### Week 14-16: AI Agent 层
- Agent 骨架（最关键）
- Plan Generator + SSE
- SimPy 执行层 + Terminal

---

## 📖 详细文档

- [后端详细设计方案](backend_design_plan.md) - 完整技术实现
- [数据库设计](../database/) - PG/Mongo/Redis 方案
- [AI Agent 设计](../AI/) - LangGraph/SimPy 架构

---

## 🔗 相关资源

- **FastAPI**: https://fastapi.tiangolo.com/
- **LangGraph**: https://langchain-ai.github.io/langgraph/
- **SimPy**: https://simpy.readthedocs.io/
- **Celery**: https://docs.celeryq.dev/
