# 微服务架构图与协作流程说明

## 一、文档目标

本文档基于现有 `docs/design/development_plan_llm.md`、`docs/design/backend/backend_design_plan.md`、`docs/design/AI/ai_simulation_agent_design.md`、`docs/design/database/database_construction_plan.md` 中的设计内容，整理出项目的微服务架构视图。

本文重点说明三件事：

1. 项目在微服务架构下的服务边界与职责划分
2. 各服务之间的协作流程
3. 各链路使用的通信方式与协议

---

## 二、架构定位

本项目是一个对标 Visual Components 的工业仿真平台，但系统实现上采用微服务架构，而不是单体架构。

采用微服务架构的原因包括：

- 前端工作区、Agent 调度、仿真执行、目录管理、场景管理在职责上天然分离
- 仿真执行属于长任务和高资源消耗任务，不适合与普通 Web 请求完全混布
- Agent 层需要独立演进，后续可能切换模型、拆分 Planner/Executor、引入更多工具节点
- 文件服务、实时通信、场景存储和目录搜索的技术栈差异明显，独立服务更利于扩展
- 后续要支持多人协同、长连接、异步仿真、任务回放和外部系统集成，微服务边界更清晰

---

## 三、微服务总体架构图

```text
+----------------------------------------------------------------------------------+
|                                  Browser / Frontend                              |
|        Next.js Workspace: eCatalog / 3D Viewport / Properties / AI Chat / Terminal |
+------------------------------------+---------------------------------------------+
                                     |
                                     | HTTPS REST / SSE / WebSocket
                                     v
+----------------------------------------------------------------------------------+
|                            API Gateway / Reverse Proxy                           |
|                           Nginx / Edge Gateway / Routing                         |
+----------------+----------------+----------------+----------------+---------------+
                 |                |                |                |
                 | REST           | REST           | SSE            | WebSocket
                 v                v                v                v
      +----------------+ +----------------+ +----------------+ +----------------+
      | Auth Service   | | Scene Service  | | Agent Service  | | Realtime Hub   |
      | OAuth / JWT    | | Scene CRUD     | | LangGraph      | | WS Broadcast   |
      | Session Bridge | | Layout Load    | | Plan Generate  | | Presence/Event |
      +-------+--------+ +--------+-------+ +--------+-------+ +--------+-------+
              |                   |                 |                 |
              | SQL               | MongoDB         | Redis / Queue   | Redis
              v                   v                 v                 v
      +----------------+ +----------------+ +----------------+ +----------------+
      | PostgreSQL     | | MongoDB        | | Redis          | | Celery Broker  |
      | users/projects | | scenes/specs   | | cache/state    | | task queue     |
      | catalog index  | | agent memory   | | pub/sub        | | async dispatch |
      +----------------+ +----------------+ +----------------+ +--------+-------+
                                                                         |
                                                                         | Celery Task
                                                                         v
                                                               +----------------------+
                                                               | Simulation Service   |
                                                               | SimPy Executor       |
                                                               | Trajectory Engine    |
                                                               +----------+-----------+
                                                                          |
                                                                          | Result / Frame / Log
                                                                          v
                                                               +----------------------+
                                                               | Realtime Hub         |
                                                               | WS Push / Stream Fan |
                                                               +----------------------+

                     +--------------------+        +------------------------------+
                     | Catalog Service    |<------>| MinIO / Object Storage       |
                     | Catalog Query      |        | GLB / URDF / thumbnails      |
                     | Signed URL         |        | exported layouts / reports   |
                     +--------------------+        +------------------------------+
```

---

## 四、核心微服务划分

### 4.1 API Gateway / Reverse Proxy

职责：

- 作为浏览器统一入口
- 路由 `/api/*`、`/ws/*`、静态资源请求
- 处理 HTTPS、跨域、安全头、WebSocket upgrade
- 未来可承担限流、鉴权前置、灰度发布和服务发现接入

通信方式：

- 对前端：HTTPS
- 对内部服务：HTTP/1.1 或 HTTP/2
- 对 WebSocket：Upgrade

推荐协议：

- REST
- SSE
- WebSocket

---

### 4.2 Auth Service

职责：

- OAuth 登录接入
- 应用内 JWT / Refresh Token 颁发
- 当前用户身份校验
- 前端会话桥接

依赖：

- PostgreSQL：用户、账号映射、刷新令牌

通信方式：

- 前端到 Auth Service：REST/JSON
- 其他服务到 Auth Service：内部 REST 或共享签名校验

适用协议：

- HTTPS REST
- JWT Bearer

---

### 4.3 Catalog Service

职责：

- 提供 eCatalog 查询
- 提供设备目录、布局模板目录
- 生成模型文件的签名下载地址
- 支持关键词搜索、分类过滤、制造商过滤

依赖：

- PostgreSQL：目录索引、搜索字段、权限元数据
- MongoDB：设备规格文档
- MinIO：模型文件和缩略图
- Redis：搜索缓存

通信方式：

- 前端到 Catalog Service：REST
- Catalog Service 到 PostgreSQL/MongoDB：数据库驱动
- Catalog Service 到 MinIO：S3 API

适用协议：

- HTTPS REST
- PostgreSQL wire protocol
- MongoDB protocol
- S3-compatible API

---

### 4.4 Scene Service

职责：

- 场景 CRUD
- 设备实例增删改查
- 连接关系维护
- 布局模板加载与场景实例化
- 场景版本控制与乐观锁

依赖：

- MongoDB：场景文档、布局模板
- PostgreSQL：项目元数据、权限、场景索引
- Realtime Hub：场景变更广播

通信方式：

- 前端到 Scene Service：REST
- Scene Service 到 MongoDB：文档读写
- Scene Service 到 Realtime Hub：内部事件或 Redis Pub/Sub

适用协议：

- HTTPS REST
- MongoDB protocol
- Redis Pub/Sub

---

### 4.5 Agent Service

职责：

- 接收用户聊天请求
- 管理 Agent 会话
- 读取场景上下文、设备规格、拓扑关系
- 调用 LangGraph / LLM 生成 SimPlan
- 通过 SSE 向前端流式输出 token、patch、warning、done 事件
- 未来可拆分为 Planner Service、Tool Service、Memory Service

依赖：

- Scene Service：读取当前场景
- Catalog / Spec 数据：读取设备规则
- MongoDB：Agent 消息与长期记忆
- Redis：流式缓冲、状态同步
- LLM Provider：通义千问/OpenAI 兼容接口
- Celery / Simulation Service：提交仿真任务

通信方式：

- 前端到 Agent Service：REST + SSE
- Agent Service 到 LLM：HTTPS REST 流式接口
- Agent Service 到内部服务：REST 或内部 SDK
- Agent Service 到队列：Celery / Redis

适用协议：

- HTTPS REST
- Server-Sent Events
- Redis Pub/Sub / Queue

---

### 4.6 Simulation Service

职责：

- 接收 SimPlan
- 调度 SimPy 执行
- 调用设备轨迹算法
- 生成仿真帧数据、运行日志、统计摘要
- 支持暂停、恢复、停止和倍速

依赖：

- Celery Worker：异步执行
- Redis：任务队列、状态同步、帧缓存
- MongoDB / PostgreSQL：必要的场景和项目上下文
- Realtime Hub：日志和帧回推

通信方式：

- Agent Service 到 Simulation Service：异步任务提交
- Simulation Service 到 Realtime Hub：Redis Pub/Sub 或内部推送
- 前端控制到 Simulation Service：REST

适用协议：

- Celery task protocol
- Redis Pub/Sub
- HTTPS REST
- WebSocket

---

### 4.7 Realtime Hub

职责：

- 统一管理 WebSocket 连接
- 广播多人协同场景更新
- 推送仿真帧数据和终端日志
- 维护在线状态

依赖：

- Redis：在线状态、发布订阅

通信方式：

- 前端到 Realtime Hub：WebSocket
- 其他服务到 Realtime Hub：Redis Pub/Sub 或内部事件接口

适用协议：

- WebSocket
- Redis Pub/Sub

---

### 4.8 File Service

职责：

- 上传下载模型文件
- 管理导出文件
- 生成预签名 URL
- 管理缩略图和静态资源

依赖：

- MinIO：对象存储
- PostgreSQL：文件元信息索引

通信方式：

- 前端到 File Service：REST
- File Service 到 MinIO：S3-compatible API

适用协议：

- HTTPS REST
- S3-compatible API

---

## 五、数据存储在微服务中的分工

### PostgreSQL

存储内容：

- 用户
- 项目
- 项目成员权限
- 设备目录索引
- Agent 会话元信息
- 仿真任务记录

适合原因：

- 结构化强
- 适合搜索、过滤、JOIN 和权限模型

### MongoDB

存储内容：

- 场景文档
- 设备规格文档
- 布局模板
- Agent 消息
- SimPlan 持久化方案

适合原因：

- 文档结构灵活
- 适合嵌套 JSON、场景状态和 Agent 中间结果

### Redis

存储内容：

- 在线状态
- 实时帧缓存
- 流式 token 缓冲
- 搜索缓存
- 队列与发布订阅

适合原因：

- 低延迟
- 适合实时同步和短期状态

### MinIO

存储内容：

- GLB / URDF 模型
- 缩略图
- 导出布局 JSON
- CSV / 报告文件

适合原因：

- 文件存储和大对象管理
- 适合前端下载与静态资源访问

---

## 六、微服务协作流程

### 6.1 用户登录与进入工作区

流程：

1. 前端向 Auth Service 发起 OAuth 登录或登录桥接请求
2. Auth Service 校验身份，签发应用 JWT
3. 前端携带 JWT 访问项目工作区
4. API Gateway 将请求转发给对应服务
5. Scene Service 返回项目场景，Catalog Service 返回目录数据

通信方式：

- 浏览器 -> Auth Service：HTTPS REST
- Auth Service -> PostgreSQL：SQL
- 浏览器 -> Scene/Catalog：HTTPS REST

---

### 6.2 场景加载与协同编辑流程

流程：

1. 前端加载项目时调用 Scene Service 获取 `scene document`
2. 同时建立 `/ws/scenes/{projectId}` WebSocket 连接
3. 用户拖拽设备、修改属性时，前端向 Scene Service 发 PATCH/POST
4. Scene Service 将变更写入 MongoDB，并更新版本号
5. Scene Service 通过 Realtime Hub 广播变更给其他在线用户
6. 其他客户端接收变更后更新本地 store 和视图

通信方式：

- 前端 -> Scene Service：REST
- Scene Service -> MongoDB：文档写入
- Scene Service -> Realtime Hub：Redis Pub/Sub 或内部事件
- Realtime Hub -> 前端：WebSocket

---

### 6.3 eCatalog 查询与模型加载流程

流程：

1. 前端在 eCatalog 搜索或展开分类
2. Catalog Service 查询 PostgreSQL 索引
3. 若命中缓存，则从 Redis 返回结果
4. 若需要加载模型，Catalog/File Service 生成 MinIO 预签名 URL
5. 前端使用签名 URL 加载 GLB / URDF 模型

通信方式：

- 前端 -> Catalog Service：REST
- Catalog Service -> PostgreSQL：SQL
- Catalog Service -> Redis：缓存协议
- Catalog/File Service -> MinIO：S3 API
- 前端 -> MinIO URL：HTTPS GET

---

### 6.4 AI 聊天与 Agent 规划流程

流程：

1. 用户在 AI Chat 中输入需求
2. 前端向 Agent Service 发起 `POST /sessions/{id}/messages`
3. Agent Service 读取当前 `sessionId`、`projectId`、消息上下文
4. Agent Service 调用 Scene Service / MongoDB 读取场景信息
5. Agent Service 根据设备规格、拓扑结构和用户输入生成 SimPlan
6. Agent Service 通过 SSE 将 token、warning、patch、done 流式推送给前端
7. 如果生成了场景 patch，则 Scene Service 落库并广播

通信方式：

- 前端 -> Agent Service：HTTPS POST
- Agent Service -> 前端：SSE
- Agent Service -> Scene Service：REST 或内部 RPC
- Agent Service -> MongoDB / PostgreSQL：数据读写
- Agent Service -> LLM Provider：HTTPS REST 流式接口

---

### 6.5 仿真执行流程

流程：

1. Agent Service 或前端控制栏提交仿真执行请求
2. Simulation Service 将仿真任务发送到 Celery Broker
3. Celery Worker 拉取任务并启动 SimPy 执行
4. 仿真执行过程中持续产生日志、帧数据、统计信息
5. Worker 将帧与日志写入 Redis Stream / PubSub
6. Realtime Hub 订阅这些消息并通过 WebSocket 推送给前端
7. 前端更新 3D 动画、Terminal 输出和控制栏状态

通信方式：

- 前端/Agent -> Simulation Service：REST
- Simulation Service -> Celery：任务提交
- Celery Worker -> Redis：状态和流
- Realtime Hub -> 前端：WebSocket

---

### 6.6 文件上传与导出流程

流程：

1. 前端上传模型、缩略图或附件
2. File Service 校验文件并写入 MinIO
3. File Service 记录元数据到 PostgreSQL 或 MongoDB
4. 导出场景时，Scene Service / Simulation Service 生成导出文件
5. File Service 返回下载地址或预签名 URL

通信方式：

- 前端 -> File Service：REST multipart/form-data
- File Service -> MinIO：S3 API
- File Service -> PostgreSQL / MongoDB：元数据写入

---

## 七、通信协议矩阵

| 通信双方 | 主要用途 | 通信方式 | 协议 |
|---|---|---|---|
| Browser -> API Gateway | 统一入口 | 同步请求 | HTTPS |
| Browser -> Auth Service | 登录/鉴权 | REST | HTTPS + JSON |
| Browser -> Scene Service | 场景 CRUD | REST | HTTPS + JSON |
| Browser -> Catalog Service | 目录查询 | REST | HTTPS + JSON |
| Browser -> Agent Service | 聊天请求 | REST | HTTPS + JSON |
| Agent Service -> Browser | 流式 token/patch | 单向流 | SSE |
| Browser -> Realtime Hub | 协同/仿真实时通道 | 双向连接 | WebSocket |
| Scene Service -> Realtime Hub | 场景变更事件 | 内部事件 | Redis Pub/Sub |
| Simulation Worker -> Realtime Hub | 帧/日志事件 | 内部事件 | Redis Pub/Sub / Stream |
| Simulation Service -> Celery Worker | 异步仿真任务 | 队列 | Celery over Redis |
| Catalog/Scene/Auth -> PostgreSQL | 结构化数据读写 | 数据库连接 | PostgreSQL protocol |
| Scene/Agent -> MongoDB | 文档读写 | 数据库连接 | MongoDB protocol |
| 多服务 -> Redis | 缓存、状态、广播 | 数据访问 | Redis protocol |
| File/Catalog -> MinIO | 文件读写、签名 URL | 对象存储访问 | S3-compatible API |
| Agent Service -> LLM Provider | 模型调用 | REST 流式请求 | HTTPS + JSON / SSE-style stream |

---

## 八、推荐的服务拆分优先级

当前项目在实现上仍可能先以“模块化单仓服务”推进，但从微服务演进角度，推荐拆分顺序如下：

### 第一阶段：逻辑分层

- Auth 模块
- Catalog 模块
- Scene 模块
- Agent 模块
- Simulation 模块
- File 模块

目标：

- 在同一 FastAPI 工程内完成边界清晰的模块拆分

### 第二阶段：长任务与实时链路独立

- Simulation Worker 独立进程
- Realtime Hub 独立部署
- Redis/Celery 形成稳定异步链路

目标：

- 先把高资源消耗任务与普通 API 请求分离

### 第三阶段：Agent 独立服务化

- Agent Service 独立部署
- 与 Scene/Catalog/Auth 通过内部 REST 或 RPC 协作

目标：

- 支持模型切换、Agent 水平扩容、推理链路演进

### 第四阶段：完整微服务化

- Gateway
- Auth
- Catalog
- Scene
- Agent
- Simulation
- Realtime
- File

目标：

- 面向生产部署和团队并行开发

---

## 九、架构设计原则

### 9.1 场景编辑和仿真执行解耦

场景编辑属于高频、小事务、强一致性需求；
仿真执行属于长任务、异步、资源消耗型任务。

因此两者必须拆分。

### 9.2 Agent 决策和轨迹算法解耦

Agent 负责理解需求和生成计划；
轨迹算法负责按照参数执行。

这样可以保证：

- Agent 易于升级
- 仿真执行稳定可控
- 算法层不被 LLM 直接污染

### 9.3 实时链路和 CRUD 链路解耦

REST 适合管理操作；
WebSocket 适合实时协同与动画推送；
SSE 适合 AI 单向流式输出。

三者职责不同，不能混成一条通道。

### 9.4 结构化数据与文档数据分离

PostgreSQL 负责索引与关系；
MongoDB 负责灵活文档；
Redis 负责实时状态；
MinIO 负责文件。

这是当前架构里最重要的数据边界之一。

---

## 十、总结

本项目的微服务架构不是为了形式上的“拆服务”，而是由业务特性自然决定的：

- 前端工作区需要低延迟交互
- Agent 层需要流式响应和复杂上下文推理
- 仿真层需要异步执行和高资源隔离
- 多人协同需要实时广播
- 场景、目录、文件和权限数据的存储模型不同

因此系统最合理的形态，就是一个以 API Gateway 为入口、以 Auth / Catalog / Scene / Agent / Simulation / File / Realtime 为核心服务的微服务体系。

从协作角度看：

- REST 负责管理与提交
- SSE 负责 Agent 流式输出
- WebSocket 负责协同和仿真实时反馈
- Redis/Celery 负责异步任务与服务间解耦
- PostgreSQL / MongoDB / MinIO 分别承担结构化、文档化和文件化存储职责

这套架构既能支撑当前的前端工作区开发，也为后续完整对标 Visual Components、接入新一代 Agent 和仿真执行引擎提供了清晰的演进路径。
