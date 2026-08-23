# 系统目录结构设计

**文档版本**: v1.0  
**创建日期**: 2026-04-16  
**用途**: 定义对标 Visual Components 4.8 的 Web 原生仿真平台在代码仓库中的整体目录组织方式，作为后续分阶段开发的统一落地基线。

---

## 1. 设计目标

本目录结构服务于以下目标：

- 支撑前端、后端、AI Agent、仿真引擎并行开发
- 将“调度层”和“执行层”在代码层面彻底拆开
- 让共享契约（Scene / SimPlan / WebSocket Event）有统一归档位置
- 让部署、种子数据、测试与业务代码解耦
- 便于按阶段推进，不会因为前期目录随意扩张而影响后续重构

---

## 2. 顶层目录结构

```text
Agentic Components/
├── docs/                              # 项目文档中心
│   ├── README.md
│   ├── product_comparison.md
│   └── design/
│       ├── development_plan_llm.md
│       ├── system_directory_structure.md
│       ├── frontend/
│       ├── backend/
│       ├── database/
│       └── AI/
│
├── frontend/                          # Next.js 16 + React 19 + R3F 前端
│   ├── app/
│   ├── components/
│   ├── hooks/
│   ├── stores/
│   ├── services/                      # 前端 API / SSE / WebSocket 封装
│   ├── lib/                           # 通用工具、three 辅助函数
│   ├── styles/
│   ├── types/
│   ├── public/
│   └── tests/
│
├── backend/                           # FastAPI + LangGraph + SimPy 后端
│   ├── main.py
│   ├── config.py
│   ├── api/
│   ├── services/
│   ├── repositories/                  # 数据访问层，屏蔽 PG / Mongo / Redis 细节
│   ├── models/
│   ├── schemas/
│   ├── core/
│   ├── agents/                        # AI 调度层
│   ├── simulation/                    # SimPy 执行层
│   ├── workers/                       # Celery worker 启动与任务装配
│   ├── scripts/
│   └── tests/
│
├── packages/                          # 跨端共享契约与公共模块
│   ├── contracts/                     # Scene / SimPlan / Event JSON Schema
│   ├── shared-types/                  # TS 类型与字段常量
│   └── ui-tokens/                     # 颜色、尺寸、面板布局常量
│
├── infra/                             # 本地开发与生产部署基础设施
│   ├── docker/
│   ├── nginx/
│   ├── compose/
│   ├── env/
│   └── monitoring/
│
├── scripts/                           # 仓库级脚本
│   ├── dev/                           # 本地启动、环境检查
│   ├── seed/                          # 种子数据导入
│   ├── build/                         # 构建与导出
│   └── release/                       # 打包与发布辅助
│
├── data/                              # 开发期数据样例与导入模板
│   ├── seed/
│   ├── fixtures/
│   └── examples/
│
├── tests/                             # 端到端、集成、性能测试
│   ├── e2e/
│   ├── integration/
│   └── performance/
│
├── .env.example
├── docker-compose.yml
├── pnpm-workspace.yaml
├── README.md
└── AGENT.md
```

---

## 3. 关键目录说明

### 3.1 `docs/`

用于承载产品、架构、数据库、Agent、阶段计划等全部设计文档。  
其中 `docs/design/system_directory_structure.md` 是“代码仓库如何落地”的总索引，后续每个阶段新增子模块时都以此为基准。

### 3.2 `frontend/`

前端聚焦五大工作区能力：

- eCatalog 目录检索与拖拽入场
- 3D Scene 视口渲染与设备操作
- Properties Panel 动态表单
- AI Chat 流式交互
- Terminal Panel 仿真日志与结果回显

推荐子结构如下：

```text
frontend/
├── app/                              # App Router 页面入口
├── components/
│   ├── layout/
│   ├── ecatalog/
│   ├── viewport/
│   ├── properties/
│   ├── ai-chat/
│   └── terminal/
├── hooks/
├── stores/
├── services/
│   ├── api/                          # REST 请求
│   ├── sse/                          # Agent SSE 流
│   └── websocket/                    # 场景与仿真实时连接
├── lib/
│   ├── three/
│   ├── drag-drop/
│   └── utils/
├── styles/
├── types/
└── tests/
```

### 3.3 `backend/`

后端拆为四层：

- `api/`：只处理协议层、鉴权、请求响应
- `services/`：承载业务编排
- `repositories/`：统一封装 PostgreSQL / MongoDB / Redis 访问
- `agents/` 与 `simulation/`：分别对应 AI 调度层和仿真执行层

推荐子结构如下：

```text
backend/
├── api/
│   ├── auth.py
│   ├── projects.py
│   ├── scenes.py
│   ├── catalog.py
│   ├── agent.py
│   ├── simulation.py
│   └── files.py
├── services/
│   ├── project_service.py
│   ├── scene_service.py
│   ├── catalog_service.py
│   ├── layout_service.py
│   ├── agent_service.py
│   └── simulation_service.py
├── repositories/
│   ├── pg/
│   ├── mongo/
│   ├── redis/
│   └── minio/
├── models/
│   ├── pg/
│   └── mongo/
├── schemas/
├── core/
├── agents/
│   └── simulation/
│       ├── graph.py
│       ├── state.py
│       ├── nodes/
│       ├── tools/
│       └── prompts/
├── simulation/
│   ├── engine.py
│   ├── algorithms/
│   ├── events/
│   ├── reporters/
│   └── tasks.py
├── workers/
├── scripts/
└── tests/
```

### 3.4 `packages/`

这个目录用于解决跨端重复定义问题，是整个系统后期可维护性的关键。

- `contracts/`：统一存放 `scene.schema.json`、`simplan.schema.json`、`ws-events.schema.json`
- `shared-types/`：前端常量、枚举、事件名等共享定义
- `ui-tokens/`：工业风 UI 变量，保证前端主题一致

这样可以避免：

- 前后端字段名不一致
- SSE / WebSocket 事件名散落多处
- SimPlan 结构一改就全链路连锁修改

### 3.5 `infra/`

用于管理环境和部署，不与业务代码混放。

```text
infra/
├── docker/                           # 各服务 Dockerfile
├── compose/                          # 开发/测试/生产 compose 拆分
├── nginx/                            # 反向代理、静态资源、WS 转发
├── env/                              # 环境变量模板
└── monitoring/                       # 日志、指标、健康检查配置
```

### 3.6 `scripts/` 与 `data/`

- `scripts/` 存放“执行逻辑”
- `data/` 存放“输入样例”

两者分离后，后续做设备种子导入、布局模板初始化、性能测试数据生成时会更清晰。

### 3.7 `tests/`

仓库级测试建议独立于 `frontend/` 与 `backend/` 局部测试，专门承载跨模块验证：

- `e2e/`：用户视角完整流程
- `integration/`：前后端、数据库、Redis、MinIO 联调
- `performance/`：3D 设备数量、SSE 首 token、仿真吞吐性能

---

## 4. 与分阶段开发的映射关系

### Phase 1：前端可演示

优先落地以下目录：

- `frontend/`
- `packages/ui-tokens/`
- `packages/shared-types/`
- `docs/`

### Phase 2：数据与基础设施就绪

新增并稳定以下目录：

- `infra/`
- `scripts/seed/`
- `data/seed/`
- `backend/models/`
- `backend/repositories/`

### Phase 3：后端 API 完整

重点补齐：

- `backend/api/`
- `backend/services/`
- `backend/core/`
- `backend/tests/`

### Phase 4：AI 仿真全链路

重点补齐：

- `backend/agents/`
- `backend/simulation/`
- `backend/workers/`
- `packages/contracts/`

### Phase 5：生产与验证

重点补齐：

- `tests/e2e/`
- `tests/integration/`
- `tests/performance/`
- `infra/monitoring/`
- `scripts/release/`

---

## 5. 目录约束建议

为避免后期目录失控，建议在实现阶段遵守以下约束：

- 前端页面入口只放在 `frontend/app/`，业务组件不得回流到页面目录
- 后端路由层不得直接操作数据库，统一经 `services/` + `repositories/`
- Agent 节点、工具、Prompt 必须分目录，不能全部堆进一个文件
- SimPy 轨迹算法必须独立于 Agent 生成逻辑，保证“计划生成”和“执行计算”解耦
- 大模型文件、GLB、URDF、缩略图不直接提交到仓库，仓库只保留示例数据或清单，实际文件走 MinIO

---

## 6. 推荐的下一步文档拆分

在该目录结构确定后，建议下一步按以下顺序继续补文档：

1. `frontend/` 真实工程目录初始化清单
2. `backend/` 真实工程目录初始化清单
3. `packages/contracts/` 契约文件清单
4. `infra/` 的 Docker 与环境变量规划
5. `tests/` 的分层测试策略

---

## 7. 结论

这份目录结构的核心目的不是“先把文件夹列出来”，而是先把系统边界定清楚：

- `frontend/` 负责交互与渲染
- `backend/agents/` 负责理解和生成计划
- `backend/simulation/` 负责执行计划
- `packages/contracts/` 负责统一语言
- `infra/` 负责让系统可以稳定跑起来

后续所有分阶段开发，都建议严格围绕这套边界推进，避免在 Week 8 之后因为目录和职责混乱而产生大规模重构。
