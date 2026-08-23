# 工业三维可视化仿真平台 · 完整开发计划

**文档版本**: v1.0  
**创建日期**: 2026-04  
**文档用途**: 大模型可读的系统设计与开发计划参考文档  
**总开发周期**: 17 周，5 个阶段，5 个里程碑

---

## 目录

1. [项目定位与核心差异化](#1-项目定位与核心差异化)
2. [系统架构](#2-系统架构)
3. [前端设计方案](#3-前端设计方案)
4. [数据库设计方案](#4-数据库设计方案)
5. [后端 API 设计方案](#5-后端-api-设计方案)
6. [AI Agent 仿真架构](#6-ai-agent-仿真架构)
7. [开发阶段规划](#7-开发阶段规划)
8. [技术风险与应对](#8-技术风险与应对)
9. [完整依赖清单](#9-完整依赖清单)

---

## 1. 项目定位与核心差异化

### 1.1 平台定位

本平台对标 Visual Components 4.8（工业三维仿真软件），实现为 Web 原生的工业车间三维可视化与仿真平台。核心创新在于用 LLM-Agent 替代 VC 的手动 Python Script Behavior，实现自然语言驱动的设备工艺建模与仿真调度。

### 1.2 与 VC 4.8 功能对照

| VC 4.8 模块 | 功能描述 | 本平台策略 |
|---|---|---|
| eCatalog（电子目录） | 3500+ 预定义设备库，Smart Collection，本地/远程源 | 云端动态目录，PostgreSQL 索引 + MinIO 文件存储 |
| Layout Configuration（布局配置） | 拖拽摆放设备，CAD 导入，多选操作 | Web 原生拖拽，React Three Fiber 渲染 |
| 3D 操作 | 旋转/平移/缩放，Cell Graph，Simulation Controls | OrbitControls + Transform Gizmo，R3F Canvas |
| 组件属性面板 | 默认/Advanced/Materials 三 Tab | 默认/仿真 两 Tab，JSON Schema 驱动动态渲染 |
| 组件建模 | 手动 Python Script Behavior，门槛高 | **颠覆**：LangGraph Agent + Skills 规范 |
| 工艺建模 | Flow/Product/Statement 手动配置 | **颠覆**：Agent 自动生成工艺配置 |
| 仿真引擎 | VC 内置时序仿真核心 | **颠覆**：AI 调度层（SimPlan）+ SimPy 执行层 |

### 1.3 支持的设备类型（当前版本）

平台当前支持四类工业设备，每类设备有独立的参数规范和仿真轨迹算法：

#### 1.3.1 传送带（conveyor）

```json
{
  "device_type": "conveyor",
  "model_format": "glb",
  "default_params": {
    "id": "",
    "type": "conveyor",
    "nodeName": "",
    "ConveyorLength": 1000,
    "ConveyorWidth": 600,
    "ConveyorHeight": 800,
    "ConveyorSpeed": 200,
    "liftoffset": 0
  },
  "simulation_params": {
    "conveyorStartOffset": 0,
    "conveyorEndOffset": 0
  },
  "constraints": {
    "ConveyorSpeed": { "min": 50, "max": 2000, "unit": "mm/s" },
    "ConveyorLength": { "min": 100, "max": 10000, "unit": "mm" }
  }
}
```

#### 1.3.2 机械臂（robot）

```json
{
  "device_type": "robot",
  "model_format": "urdf",
  "default_params": {
    "id": "",
    "type": "robot",
    "nodeName": ""
  },
  "simulation_params": {
    "speed": 1.5,
    "joints": [
      { "name": "joint_1", "nodeName": "Link1_00In", "type": "revolute",
        "axis": { "x": 0, "y": 1, "z": 0 }, "limit": { "lower": -3.14, "upper": 3.14 } },
      { "name": "joint_2", "nodeName": "Link2_00Jn", "type": "revolute",
        "axis": { "x": 0, "y": 0, "z": 1 }, "limit": { "lower": -1.57, "upper": 2.36 } },
      { "name": "joint_3", "nodeName": "Link3_00Kn", "type": "revolute",
        "axis": { "x": 0, "y": 0, "z": 1 }, "limit": { "lower": -1.57, "upper": 2.36 } },
      { "name": "joint_4", "nodeName": "Link4_00Ln", "type": "revolute",
        "axis": { "x": 0, "y": 0, "z": 1 }, "limit": { "lower": -1.57, "upper": 2.36 } },
      { "name": "joint_5", "nodeName": "Link5_00Mn", "type": "revolute",
        "axis": { "x": 1, "y": 0, "z": 0 }, "limit": { "lower": -1.57, "upper": 2.36 } },
      { "name": "joint_6", "nodeName": "Link6_00Nn", "type": "revolute",
        "axis": { "x": 0, "y": 1, "z": 0 }, "limit": { "lower": -1.57, "upper": 2.36 } }
    ]
  },
  "constraints": {
    "speed": { "min": 0.1, "max": 10.0, "unit": "rad/s" }
  }
}
```

#### 1.3.3 升降台（lift）

```json
{
  "device_type": "lift",
  "model_format": "glb",
  "default_params": {
    "id": "",
    "type": "lift",
    "nodeName": "",
    "carrierNodeName": "Carrier_00"
  },
  "simulation_params": {
    "speed": 0.5,
    "motion": {
      "rootAxis": "x",
      "carrierAxis": "y",
      "rootRange": { "min": -4.142, "max": 0.858 },
      "carrierRange": { "min": 0.185, "max": 3.160 }
    }
  },
  "constraints": {
    "speed": { "min": 0.05, "max": 2.0, "unit": "m/s" }
  }
}
```

**注意**：升降台配置文件（如 `smart_storage_1.json`）中包含 `keyPoints` 字段，其中 `transfer_board` 节点名是轨迹算法的停靠锚点：

```json
{
  "keyPoints": [
    {
      "name": "transfer_board",
      "auto": false,
      "nodeName": "Z_00En",
      "description": "传递板位置，用于工件挂载"
    }
  ]
}
```

#### 1.3.4 仓储柜（storage）

```json
{
  "device_type": "storage",
  "model_format": "glb",
  "default_params": {
    "id": "",
    "type": "storage",
    "nodeName": ""
  },
  "simulation_params": {
    "cells": [
      { "id": "A1", "position": { "x": -1.020, "y": 1.595, "z": 0.000 } },
      { "id": "A2", "position": { "x": -1.020, "y": 2.195, "z": 0.000 } },
      { "id": "A3", "position": { "x": -2.040, "y": 2.195, "z": 0.000 } }
    ]
  },
  "constraints": {
    "max_cells": 100
  }
}
```

---

## 2. 系统架构

### 2.1 分层架构总览

```
客户端（Next.js 16）
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

### 2.2 技术选型汇总

| 层级 | 技术 | 版本 | 理由 |
|---|---|---|---|
| 前端框架 | Next.js | 16.1.6 | App Router，SSR/SSG，TypeScript |
| 3D 引擎 | React Three Fiber | ^9.5.0 | 声明式 Three.js |
| 3D 工具库 | @react-three/drei | ^10.7.7 | OrbitControls / useGLTF |
| 状态管理 | Zustand | ^5.0.11 | 轻量，适配 3D 频繁更新 |
| 布局分割 | react-resizable-panels | ^4.5.8 | 五区域任意调整 |
| 虚拟列表 | @tanstack/react-virtual | ^3.13.0 | eCatalog 大目录性能 |
| URDF 加载 | urdf-loader | ^0.12.6 | 机械臂模型 |
| Web 框架 | FastAPI | 0.115.0 | 异步，原生 SSE/WebSocket |
| PG ORM | SQLAlchemy | 2.0.35 | 异步，连接池 |
| Mongo ODM | Motor | 3.5.0 | 异步 MongoDB |
| Agent 框架 | LangGraph | 0.2.35 | 有状态多节点图 |
| LLM 路由 | LiteLLM | 1.50.0 | 多模型切换 |
| 仿真引擎 | SimPy | 4.1.1 | 事件驱动离散仿真 |
| 任务队列 | Celery + Redis | 5.4.0 | 仿真异步计算 |
| 对象存储 | MinIO | 7.2.9 | GLB/URDF 文件 |

### 2.3 数据库分工原则

```
PostgreSQL   ← 目录索引层（用户/项目/权限/设备目录/布局目录）
               所有可被 WHERE/JOIN/全文索引的字段
MongoDB      ← 文档存储层
               scenes：场景完整文档（设备实例嵌套，Schema 可变）
               device_specs：设备参数规范模板
               layout_templates：预设布局方案（scene.json 格式）
               agent_messages：Agent 对话消息
Redis        ← 运行时状态（WebSocket 在线/仿真帧/搜索缓存/Agent Token 缓冲）
MinIO        ← 文件存储（GLB/URDF 模型文件/缩略图/导出文件）
```

**分工依据**：场景文档中设备实例嵌套深（几何体 + 运动学 + 工艺行为三棵子树），MongoDB 的 `$set` 路径更新对这种结构的局部更新性能远优于 PostgreSQL JSONB。两者通过相同 UUID 关联，搜索走 PG，读参数走 MongoDB。

---

## 3. 前端设计方案

### 3.1 布局结构

```
┌─────────────────────────────────────────────────────────────────┐
│  TopBar（菜单工具栏，固定高度）                                   │
├──────────────┬──────────────────────────────┬───────────────────┤
│              │  SimulationBar（浮层覆盖）    │                   │
│  eCatalog    │  ▶ ⏸ ⏹  00:00:00  ×1.0      │  Properties Panel │
│  Panel       │                              │  + AI Chat Panel  │
│  ─────────   │   3D Viewport                │  ───────────────  │
│  目录树      │   React Three Fiber          │  坐标 Widget      │
│  ─────────   │   OrbitControls              │  [默认|仿真] Tab  │
│  设备网格    │   GridFloor                  │  ───────────────  │
│  (虚拟化)    │   DeviceMesh × N             │  AI 聊天面板      │
│              │   Transform Gizmo            │  流式打字机输出   │
├──────────────┴──────────────────────────────┴───────────────────┤
│  Terminal Panel（可调高）：布局加载日志 + SimPy 仿真日志         │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 目录结构

```
frontend/
├── app/
│   ├── layout.tsx
│   └── workspace/[projectId]/page.tsx      # 主工作区
├── components/
│   ├── layout/
│   │   ├── WorkspaceLayout.tsx             # react-resizable-panels 五区域
│   │   ├── TopBar.tsx
│   │   └── SimulationBar.tsx               # 浮层仿真控制条
│   ├── ecatalog/
│   │   ├── ECatalogPanel.tsx
│   │   ├── CollectionsTree.tsx             # @radix-ui/react-collapsible
│   │   ├── DeviceGrid.tsx                  # @tanstack/react-virtual 虚拟化
│   │   ├── DeviceCard.tsx                  # draggable，dataTransfer 传 deviceId
│   │   └── SearchBar.tsx
│   ├── viewport/
│   │   ├── Viewport3D.tsx                  # R3F Canvas，onDrop + Raycasting
│   │   ├── SceneContent.tsx
│   │   ├── GridFloor.tsx
│   │   ├── DeviceInstance.tsx              # useGLTF（GLB）/ URDFLoader（URDF）
│   │   ├── DeviceInstances.tsx
│   │   └── TransformGizmo.tsx
│   ├── properties/
│   │   ├── PropertiesPanel.tsx             # @radix-ui/react-tabs
│   │   ├── CoordinateWidget.tsx            # X/Y/Z + Rx/Ry/Rz，三种坐标系
│   │   ├── tabs/
│   │   │   ├── DefaultTab.tsx              # 名称/类别 + 类型特有字段
│   │   │   └── SimulationTab.tsx           # 四类设备各自的仿真参数渲染
│   │   └── fields/
│   │       ├── PropRowText.tsx
│   │       ├── PropRowNumber.tsx           # 带单位的数字输入
│   │       └── PropRowSelect.tsx
│   ├── ai-chat/
│   │   ├── AIChatPanel.tsx
│   │   ├── MessageList.tsx
│   │   ├── StreamMessage.tsx               # RAF 打字机效果
│   │   └── ChatInput.tsx                   # textarea 自动增高
│   └── terminal/
│       ├── TerminalPanel.tsx
│       └── LogLine.tsx                     # ansi-to-html 着色
├── stores/
│   ├── sceneStore.ts                       # Zustand + immer
│   ├── catalogStore.ts
│   ├── simulationStore.ts
│   └── agentStore.ts
├── hooks/
│   ├── useTypewriter.ts                    # RAF 打字机 Hook
│   ├── useAgentStream.ts                   # Fetch + ReadableStream SSE
│   └── useTerminalStream.ts               # WebSocket 日志流
└── types/
    ├── scene.ts                            # DeviceInstance / Transform / Connection
    ├── catalog.ts
    └── agent.ts
```

### 3.3 拖拽入场实现

**技术方案**：HTML5 原生 drag + Canvas `onDrop` + Raycasting（不用 @dnd-kit Droppable 覆盖 Canvas，因为 Canvas 是 `<canvas>` DOM 元素，边界计算会出问题）

```typescript
// DeviceCard：写入 deviceId 到 dataTransfer
const handleDragStart = (e: React.DragEvent) => {
  e.dataTransfer.setData("application/device-id", item.id);
  e.dataTransfer.effectAllowed = "copy";
};

// Viewport3D：Canvas onDrop 接收，Raycasting 转世界坐标
const handleCanvasDrop = (e: DragEvent) => {
  const deviceId = e.dataTransfer.getData("application/device-id");
  const rect = gl.domElement.getBoundingClientRect();
  const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
  const y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera({ x, y }, camera);
  const floorPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  const worldPos = new THREE.Vector3();
  raycaster.ray.intersectPlane(floorPlane, worldPos);
  addDevice({ catalogId: deviceId, transform: { position: [worldPos.x, 0, worldPos.z], ... } });
};
```

### 3.4 属性面板 Tab 结构

#### 3.4.1 面板整体结构

```
┌──────────────────────────────────────┐
│ 设备名称（青色）          类型标识    │  设备标题栏
├──────────────────────────────────────┤
│ 坐标系: [世界] [父系坐标] [物体]     │
│ X [___]  Y [___]  Z [___]            │  CoordinateWidget（固定）
│ Rx[___]  Ry[___]  Rz[___]            │
├──────────────────────────────────────┤
│ [  默认  ] [  仿真  ]                │  Tab 切换
├──────────────────────────────────────┤
│ 基本信息                             │
│ 名称         [______________]        │
│ 类别         conveyor (只读)         │
│ 尺寸参数                             │
│ ConveyorLength [________] mm         │  DefaultTab（类型特有字段）
│ ConveyorWidth  [________] mm         │
│ ConveyorHeight [________] mm         │
│ 运行参数                             │
│ ConveyorSpeed  [________] mm/s       │
└──────────────────────────────────────┘
```

#### 3.4.2 仿真 Tab 各类型渲染

- **conveyor**：StartOffset / EndOffset 两个数字字段
- **robot**：speed 字段 + 关节折叠列表（每轴展开显示 nodeName / axis / lower / upper）
- **lift**：rootAxis / carrierAxis 下拉 + rootRange min/max + carrierRange min/max + speed
- **storage**：货格卡片网格，每格显示 id + XYZ 坐标输入，支持增删

### 3.5 打字机效果实现

**核心原理**：SSE Fetch 累积完整文本（fullText）→ RAF 动画按 batchSize 逐步显示

```typescript
// useTypewriter.ts
// fullText 由 useAgentStream 持续追加
// 增量续打判断：target.startsWith(current) → 从断点继续，否则清空重打

// useAgentStream.ts
// fetch + ReadableStream，按行解析 SSE（data: {token}\n\n）
// 累积 token 到 accumulated，更新 store
// 不用 EventSource（不支持 POST）
```

**SSE 事件格式**（后端 → 前端）：

```
data: {"type": "token", "data": "根"}
data: {"type": "token", "data": "据"}
data: {"type": "patch", "data": {...scene_patch}}
data: {"type": "warning", "data": ["参数超范围"]}
data: {"type": "done", "data": null}
```

### 3.6 Terminal 面板

- ANSI 颜色渲染：`ansi-to-html` 库
- 自动滚底：新日志时 `bottomRef.scrollIntoView({ behavior: "smooth" })`
- WebSocket 接收后端日志流（布局加载日志 + SimPy 仿真日志）

**ANSI 颜色规范**：

| 颜色 | ANSI | 用途 |
|---|---|---|
| 蓝色 | `\x1b[34m` | Agent 调度信息 |
| 绿色 | `\x1b[32m` | 仿真时间戳 |
| 青色 | `\x1b[36m` | 设备名称 |
| 紫色 | `\x1b[35m` | 信号触发 |
| 黄色 | `\x1b[33m` | 等待/警告 |
| 红色 | `\x1b[31m` | 错误 |

---

## 4. 数据库设计方案

### 4.1 PostgreSQL 完整 Schema

```sql
-- 扩展
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 用户表
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         VARCHAR(255) UNIQUE NOT NULL,
    name          VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 项目表（1:1 对应 MongoDB scenes._id）
CREATE TABLE projects (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name           VARCHAR(255) NOT NULL,
    description    TEXT,
    owner_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scene_doc_id   VARCHAR(36),         -- MongoDB _id，与 project.id 相同
    thumbnail_key  VARCHAR(500),        -- MinIO: thumbnails/proj/{id}.jpg
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    updated_at     TIMESTAMPTZ DEFAULT NOW()
);

-- 项目成员权限
CREATE TABLE project_members (
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role        VARCHAR(20) NOT NULL CHECK (role IN ('OWNER','EDITOR','VIEWER')),
    joined_at   TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (project_id, user_id)
);

-- 设备目录（eCatalog 索引，仅存可索引字段，参数规范在 MongoDB）
CREATE TABLE device_catalog (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    device_type     VARCHAR(50) NOT NULL CHECK (device_type IN ('conveyor','robot','lift','storage')),
    manufacturer    VARCHAR(100),
    model_format    VARCHAR(10) NOT NULL DEFAULT 'glb' CHECK (model_format IN ('glb','urdf')),
    model_file_key  VARCHAR(500) NOT NULL,   -- MinIO: models/{device_type}/{id}.glb
    thumbnail_key   VARCHAR(500),            -- MinIO: thumbnails/catalog/{id}.jpg
    tags            TEXT[] DEFAULT '{}',
    is_public       BOOLEAN DEFAULT TRUE,
    spec_doc_id     VARCHAR(36),             -- 关联 MongoDB device_specs._id（同 id）
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 布局目录（eCatalog 布局文件夹，模板主体在 MongoDB）
CREATE TABLE layout_catalog (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    template_doc_id VARCHAR(36) NOT NULL,    -- MongoDB layout_templates._id
    thumbnail_key   VARCHAR(500),
    tags            TEXT[] DEFAULT '{}',
    is_public       BOOLEAN DEFAULT TRUE,
    author_id       UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Agent 会话元数据（消息明细在 MongoDB）
CREATE TABLE agent_sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id),
    title       VARCHAR(255),
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 仿真任务记录
CREATE TABLE simulation_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    started_by      UUID NOT NULL REFERENCES users(id),
    celery_task_id  VARCHAR(255),
    status          VARCHAR(20) DEFAULT 'pending'
                    CHECK (status IN ('pending','running','done','failed','cancelled')),
    duration        FLOAT,
    speed           FLOAT DEFAULT 1.0,
    stats_summary   JSONB,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    finished_at     TIMESTAMPTZ
);

-- 索引
CREATE INDEX idx_projects_owner    ON projects(owner_id);
CREATE INDEX idx_catalog_type      ON device_catalog(device_type);
CREATE INDEX idx_catalog_tags      ON device_catalog USING GIN(tags);
CREATE INDEX idx_catalog_name_trgm ON device_catalog USING GIN(name gin_trgm_ops);
CREATE INDEX idx_layout_tags       ON layout_catalog USING GIN(tags);
CREATE INDEX idx_sim_runs_project  ON simulation_runs(project_id);
CREATE INDEX idx_sim_runs_status   ON simulation_runs(status);
```

### 4.2 MongoDB Collections

#### 4.2.1 device_specs（设备参数规范，与 PG device_catalog 1:1）

```javascript
// _id = PG device_catalog.id（同一个 UUID）
{
  _id: "uuid",
  device_type: "lift",
  name: "Prorunner mk5-XL",
  manufacturer: "Qimarox",
  default_params: { /* 对应前端默认 Tab 的初始值 */ },
  simulation_params: { /* 对应前端仿真 Tab 的初始值 */ },
  constraints: { /* 供 Agent Guardian 校验用 */ },
  created_at: ISODate(...)
}
```

#### 4.2.2 scenes（场景文档，与 PG projects 1:1）

```javascript
{
  _id: "project_uuid",
  version: 42,             // 乐观锁，每次写入 +1
  name: "车间 A 布局",
  floor: { width: 50.0, depth: 30.0, grid_size: 1.0 },
  devices: [
    {
      instance_id: "inst-uuid",          // 场景内唯一
      catalog_id:  "device-catalog-uuid",
      layout_device_id: "conveyor_1",    // 布局内部 ID，仿真引擎引用
      device_type: "conveyor",
      model_format: "glb",
      transform: {
        position: [10.5, 0.0, 5.0],      // [x, y, z] 米
        rotation: [0.0, 1.5708, 0.0],    // Euler rad
        scale: [1.0, 1.0, 1.0]
      },
      default_params: { /* 用户在默认 Tab 编辑的当前值 */ },
      simulation_params: { /* 用户在仿真 Tab 编辑的当前值 */ },
      process_config: {
        behaviors: [ { type: "transport", ... } ],
        states: ["idle", "running", "fault"],
        signals: { input: ["start"], output: ["done"] }
      },
      visible: true,
      locked: false
    }
  ],
  connections: [
    {
      id: "conn-001",
      from_instance: "inst-uuid-001",
      to_instance: "inst-uuid-002",
      type: "material_flow",
      label: "零件流"
    }
  ],
  simulation_config: {
    duration: 3600.0,
    warm_up: 0.0,
    random_seed: 42,
    speed_multiplier: 1.0,
    workflow: [ /* 布局工作流描述，供仿真引擎使用 */ ],
    topology: [ /* 布局拓扑关系 */ ]
  },
  source_layout_id: "layout-uuid",      // 记录来源布局
  updated_at: ISODate(...)
}
```

#### 4.2.3 layout_templates（预设布局方案）

```javascript
// 完整存储 scene.json 格式 + 数据库元信息
{
  _id: "layout-uuid",
  version: "1.0",
  name: "智能仓储流水线",
  description: "物料首先通过传送带传递给升降台...",
  devices: [
    {
      id: "conveyor_1",
      label: "入口传送带",
      // configFile 三种格式：
      // "catalog:{catalog_id}" → 引用 PG device_catalog
      // "spec:{spec_doc_id}"   → 引用 MongoDB device_specs
      // "file:devices/xxx.json" → MinIO 独立文件
      configFile: "catalog:uuid-conveyor-standard",
      param_overrides: {
        default_params: { ConveyorLength: 2000 }   // 可选，覆盖默认值
      },
      transform: { position: [10.0, 0.0, 0.0], rotation: [0,0,0], scale: [1,1,1] }
    }
  ],
  topology: [
    { from: "conveyor_1", to: "smart_storage_1", relation: "feeds",
      description: "传送带将物料输送至传送带出口" }
  ],
  workflow: [
    "传送带1将物料输送到出口位置",
    "升降台1移动到传送带出口位置获取物料",
    "升降台1将物料送达仓储柜的指定格子"
  ],
  created_at: ISODate(...)
}
```

#### 4.2.4 agent_messages（对话消息）

```javascript
{
  _id: "msg-uuid",
  session_id: "session-uuid",
  project_id: "project-uuid",
  role: "assistant",           // "user" | "assistant"
  content: "已为机械臂-01 配置抓取工艺...",
  applied_patches: [ { instance_id: "...", field: "process_config", summary: "..." } ],
  agent_trace: { intent: {...}, device_category: "robot", validation_pass: true },
  created_at: ISODate(...)
}
```

### 4.3 Redis 键设计

```
ws:online:{project_id}              SET<user_id>         在线用户
sim:state:{project_id}              HASH                 仿真运行状态
    status / sim_time / speed / task_id
sim:frames:{project_id}             STREAM(限1000条)     仿真帧数据
catalog:search:{md5(query)}         STRING(JSON) TTL:300s eCatalog 搜索缓存
catalog:category:list               STRING(JSON) TTL:3600s
scene:version:{project_id}          STRING               乐观锁版本号
agent:stream:{session_id}           LIST<token>  TTL:600s Token 缓冲
```

### 4.4 MinIO Bucket 结构

```
models/
├── conveyor/{catalog_id}.glb
├── robot/{catalog_id}.urdf
│   └── {catalog_id}/meshes/       URDF 引用的网格文件
├── lift/{catalog_id}.glb
└── storage/{catalog_id}.glb

thumbnails/
├── catalog/{catalog_id}.jpg       设备预览图 240×240
└── projects/{project_id}.jpg      项目缩略图 480×270

exports/                           TTL 24h
└── {project_id}/
    ├── layout_{timestamp}.json
    └── bom_{timestamp}.csv
```

### 4.5 点击设备的数据流

```
用户点击 3D 场景中的设备
    │
    ▼
前端 sceneStore.selectedId = instance_id
    │
    ▼
PropertiesPanel 从 sceneStore.devices 中 find(instance_id)
    │  本地已有完整参数，无额外网络请求
    ▼
渲染 CoordinateWidget + DefaultTab + SimulationTab
```

**设计依据**：场景首次加载时 `GET /api/projects/{id}/scene` 返回完整 SceneDocument（含所有设备的 default_params + simulation_params），前端全量缓存到 Zustand store。点击任意设备是 O(n) 本地查找，无网络延迟。

---

## 5. 后端 API 设计方案

### 5.1 目录结构

```
backend/
├── main.py                        # FastAPI 入口，lifespan，中间件，路由注册
├── config.py                      # env 读取
├── dependencies.py                # get_current_user / require_editor
├── api/
│   ├── auth.py                    # 认证
│   ├── scenes.py                  # 场景 CRUD + WebSocket
│   ├── catalog.py                 # eCatalog + 模型文件
│   ├── agent.py                   # Agent 会话 + SSE
│   ├── simulation.py              # 仿真控制 + 日志 WebSocket
│   └── files.py                   # 文件上传/下载
├── services/
│   ├── scene_service.py
│   ├── catalog_service.py
│   ├── layout_service.py          # instantiate_layout：布局 → 场景实例化
│   ├── agent_service.py
│   ├── simulation_service.py
│   └── file_service.py
├── agents/
│   ├── simulation/
│   │   ├── graph.py               # LangGraph 图定义
│   │   ├── state.py               # SimAgentState TypedDict
│   │   ├── nodes/
│   │   │   ├── orchestrator.py    # ReAct 主节点
│   │   │   ├── plan_generator.py
│   │   │   ├── plan_validator.py
│   │   │   ├── executor.py
│   │   │   └── clarifier.py       # Human-in-loop 中断节点
│   │   └── skills/
│   │       ├── read_scene_config.py
│   │       ├── analyze_topology.py
│   │       ├── select_device_algorithm.py
│   │       ├── resolve_device_params.py
│   │       └── generate_coordination_rules.py
├── simulation/
│   ├── engine.py                  # WorkshopSimulation（SimPy）
│   ├── tasks.py                   # Celery 任务
│   └── algorithms/
│       ├── conveyor.py            # continuous_transport
│       ├── lift.py                # lift_xy_trajectory（对接 keyPoints）
│       └── storage.py             # cell_allocation_fifo
├── models/
│   ├── pg/                        # SQLAlchemy ORM
│   └── mongo/                     # Pydantic 文档模型
├── core/
│   ├── database.py                # 连接池
│   ├── minio_client.py
│   ├── ws_manager.py              # WebSocket 连接管理器
│   └── auth.py
└── migrations/                    # Alembic
```

### 5.2 完整 API 接口

#### 认证

```
POST /api/auth/register
POST /api/auth/login        → 返回 JWT
POST /api/auth/refresh
GET  /api/auth/me
```

#### 项目管理

```
GET    /api/projects
POST   /api/projects
GET    /api/projects/{id}
PUT    /api/projects/{id}
DELETE /api/projects/{id}
GET    /api/projects/{id}/members
POST   /api/projects/{id}/members
PATCH  /api/projects/{id}/members/{user_id}
DELETE /api/projects/{id}/members/{user_id}
```

#### 场景管理

```
GET    /api/projects/{id}/scene                          → 完整 SceneDocument
PATCH  /api/projects/{id}/scene                          → JSON Patch (RFC 6902)，version 乐观锁
POST   /api/projects/{id}/scene/devices                  → 添加设备实例
PATCH  /api/projects/{id}/scene/devices/{instance_id}    → 更新变换/参数
DELETE /api/projects/{id}/scene/devices/{instance_id}
POST   /api/projects/{id}/scene/connections
DELETE /api/projects/{id}/scene/connections/{conn_id}
POST   /api/projects/{id}/scene/load-layout              → { layout_id } 布局实例化

WS /ws/scenes/{project_id}?token={jwt}
# 广播消息类型：device_added / device_updated / device_deleted
#               connection_added / user_joined / user_left
```

#### eCatalog

```
GET /api/catalog?category=&manufacturer=&q=&page=&page_size=
GET /api/catalog/{id}
GET /api/catalog/{id}/model              → MinIO 预签名 URL（GLB/URDF）
GET /api/catalog/categories
GET /api/catalog/manufacturers
GET /api/device-specs/{category}         → default_schema + simulation_schema（前端属性面板用）
GET /api/layouts                         → 布局目录列表
GET /api/layouts/{id}                    → 完整布局模板
```

#### Agent 仿真

```
POST /api/agent/sessions                 → { project_id } 创建会话
GET  /api/agent/sessions/{id}/messages   → 历史消息
POST /api/agent/sessions/{id}/messages   → SSE 流式响应（text/event-stream）
DELETE /api/agent/sessions/{id}
```

#### 仿真控制

```
POST /api/projects/{id}/simulation/start    → { speed_multiplier }
POST /api/projects/{id}/simulation/pause
POST /api/projects/{id}/simulation/resume
POST /api/projects/{id}/simulation/stop
GET  /api/projects/{id}/simulation/status
GET  /api/projects/{id}/simulation/stats

WS /ws/simulation/{project_id}?token={jwt}
# 消息类型：log（Terminal 日志）/ frame（仿真帧，驱动 3D 动画）/ done（统计摘要）
```

#### 文件服务

```
POST /api/files/upload                      → multipart，返回 file_key
GET  /api/files/{key}/presigned             → 预签名下载 URL（TTL 1h）
POST /api/projects/{id}/export/layout       → 导出 JSON
POST /api/projects/{id}/export/bom          → 导出 CSV
```

### 5.3 布局实例化逻辑

```python
async def instantiate_layout(layout_id: str, project_id: str) -> dict:
    template = await mongo.layout_templates.find_one({"_id": layout_id})
    device_instances = []

    for dev_ref in template["devices"]:
        config_file = dev_ref["configFile"]

        # 解析 configFile 引用格式
        if config_file.startswith("catalog:"):
            catalog_id = config_file.split("catalog:")[1]
            spec = await mongo.device_specs.find_one({"_id": catalog_id})
        elif config_file.startswith("file:"):
            spec = await minio_client.get_json(key=config_file.split("file:")[1])

        # 合并默认值 + 布局覆盖
        overrides = dev_ref.get("param_overrides", {})
        default_params = { **spec["default_params"], **overrides.get("default_params", {}),
                           "id": str(uuid4()), "nodeName": dev_ref["label"] }
        simulation_params = { **spec["simulation_params"],
                              **overrides.get("simulation_params", {}) }

        device_instances.append({
            "instance_id": default_params["id"],
            "layout_device_id": dev_ref["id"],   # 保留布局内部 ID
            "device_type": spec["device_type"],
            "transform": dev_ref["transform"],
            "default_params": default_params,
            "simulation_params": simulation_params,
            ...
        })

    # 从 topology 生成 connections
    connections = build_connections_from_topology(template["topology"], device_map)

    # 写入 MongoDB scenes
    await mongo.scenes.insert_one({ "_id": project_id, "devices": device_instances,
                                    "connections": connections, ... })
```

---

## 6. AI Agent 仿真架构

### 6.1 核心原则：调度与执行分离

```
用户输入
    │
    ▼
AI 调度层（LangGraph Agent）
    理解意图 → 读场景文件 → 分析拓扑 → 选择算法 → 生成 SimPlan JSON
    │
    │ SimPlan JSON（两层之间的唯一接口）
    ▼
执行层（SimPy + 轨迹算法）
    ConveyorProcess  → continuous_transport 算法
    LiftProcess      → lift_xy_trajectory 算法（对接 keyPoints.transfer_board）
    StorageProcess   → cell_allocation_fifo 算法
    │
    ├── 帧数据 → WebSocket → 3D 动画
    └── 日志   → WebSocket → Terminal Panel
```

### 6.2 SimAgentState 完整定义

```python
class SimAgentState(TypedDict):
    # 输入
    session_id: str
    project_id: str
    user_message: str
    uploaded_docs: list[str]              # MinIO key 列表

    # LangGraph 消息历史（自动 append）
    messages: Annotated[list, add_messages]

    # 解析结果
    intent: Optional[dict]
    input_complexity: Literal["simple", "medium", "detailed"]

    # 场景信息（Skills 工具读取后存入）
    scene_doc: Optional[dict]
    device_configs: dict[str, dict]        # device_id → 完整配置
    topology_order: list[str]              # 拓扑排序执行顺序

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

### 6.3 LangGraph 完整图定义

```python
def build_sim_graph():
    # 工具绑定
    tools = [read_scene_config, analyze_topology, select_device_algorithm,
             resolve_device_params, generate_coordination_rules]
    llm_with_tools = get_llm().bind_tools(tools)

    graph = StateGraph(SimAgentState)

    # 节点注册
    graph.add_node("orchestrator",    orchestrator_node)    # ReAct，调用 tools
    graph.add_node("tools",           ToolNode(tools))      # 执行工具
    graph.add_node("clarifier",       clarifier_node)       # interrupt 中断
    graph.add_node("plan_generator",  plan_generator_node)  # structured_output
    graph.add_node("plan_validator",  plan_validator_node)  # 纯逻辑校验
    graph.add_node("executor",        executor_node)        # 提交 Celery

    graph.set_entry_point("orchestrator")

    # 边定义
    graph.add_conditional_edges("orchestrator", route_orchestrator,
        { "tools": "tools", "plan_generator": "plan_generator" })

    graph.add_edge("tools", "orchestrator")                 # ReAct 循环

    graph.add_conditional_edges("plan_generator",
        lambda s: "clarifier" if s.get("pending_questions") else "plan_validator",
        { "clarifier": "clarifier", "plan_validator": "plan_validator" })

    graph.add_edge("clarifier", "orchestrator")             # 用户回答后重新处理

    graph.add_conditional_edges("plan_validator", route_after_validation,
        { "executor": "executor", "plan_generator": "plan_generator", "end": END })

    graph.add_edge("executor", END)

    memory = MemorySaver()
    return graph.compile(checkpointer=memory, interrupt_before=["clarifier"])
```

### 6.4 SimPlan 完整格式

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
      "params": { "speed": 300, "length": 2000, "part_interval": 8.0 },
      "triggers": { "start": "sim_start" },
      "continuous": true
    },
    {
      "device_id": "smart_storage_1",
      "device_type": "lift",
      "algorithm": "lift_xy_trajectory",
      "params": {
        "root_axis": "x", "carrier_axis": "y",
        "root_range": { "min": -4.142, "max": 0.858 },
        "carrier_range": { "min": 0.185, "max": 3.160 },
        "speed": 0.5,
        "home_position": { "root": 0.858, "carrier": 0.185 },
        "key_points": [
          { "name": "transfer_board", "nodeName": "Z_00En" }
        ]
      },
      "triggers": { "start": "conveyor_1.part_at_exit" },
      "continuous": false
    }
  ],
  "coordination_rules": [
    { "type": "signal", "when": "conveyor_1.part_at_exit",
      "trigger": "smart_storage_1.fetch_part",
      "description": "传送带出口有物料时，触发升降台取料" },
    { "type": "resource_wait", "resource": "storage.cells",
      "condition": "has_empty", "blocked_device": "smart_storage_1",
      "description": "仓储柜满时升降台等待" }
  ],
  "plan_summary": "智能仓储流水线仿真，传送带 300mm/s，升降台 0.5m/s，仿真 1 小时"
}
```

### 6.5 五种用户输入层级

| 级别 | 输入形式 | 示例 | Agent 策略 |
|---|---|---|---|
| Level 1 | 极简一句话 | "跑一下仿真" | 全依赖 scene.json workflow，参数取 device_specs 默认值 |
| Level 2 | 带关键参数 | "传送带 400mm/s，跑 30 分钟" | 提取数字参数覆盖默认值，其余读配置文件 |
| Level 3 | 复杂工艺逻辑 | "高峰期场景，仓满后先出库再入库" | Clarifier 追问缺失参数，生成条件分支协调规则 |
| Level 4 | 上传仿真文档 | Markdown 表格 + 入库/出库规则 + 验收标准 | Doc Parser 解析，注入 SimPy 断言检查 |
| Level 5 | 多轮对话迭代 | "增加格子到9个，重跑 / 保存为方案B" | MemorySaver 维护参数状态，支持增量修改 |

### 6.6 Terminal 三阶段输出

```
# 阶段 1：Agent 调度输出（蓝色，仿真启动前）
[Agent] 解析场景：6 个设备，5 条拓扑关系
[Agent] 执行顺序：conveyor_1 → smart_storage_1 → storage → ...
[Agent] 算法选择：conveyor_1 → continuous_transport (300mm/s)

# 阶段 2：SimPy 运行输出（绿色时间戳 + 青色设备名）
[  0.00s] conveyor_1      开始执行
[  6.67s] conveyor_1      物料 #1 到达出口
[  6.67s] 信号触发: conveyor_1.part_at_exit    （紫色）
[  7.20s] smart_storage_1 到达取料位

# 阶段 3：统计摘要（仿真结束后）
══════════════════════════
仿真完成  总时长: 3600s
conveyor_1      处理物料: 450 件 | 利用率: 92.3%
smart_storage_1 搬运次数: 448 次 | 平均周期: 7.8s
瓶颈设备: storage（满仓等待 32s）
══════════════════════════
```

### 6.7 Memory 三层设计

| 层级 | 实现 | 作用域 | 存储内容 |
|---|---|---|---|
| 短期记忆 | `MemorySaver` + `thread_id` | 同一 session | 图状态快照，支持中断恢复 |
| 中期记忆 | MongoDB `agent_messages` | 跨请求 | 消息持久化，刷新页面后历史仍在 |
| 长期记忆 | MongoDB `sim_plans` | 跨 session | 用户命名保存的仿真方案，可复用 |

---

## 7. 开发阶段规划（17 周）

### Phase 1：前端面板构建（Week 1 – Week 5）

> **目标**：不依赖任何后端，用 Mock 数据完成全部 UI 组件，可完整演示所有面板。

#### Week 1：工程初始化 + 布局骨架

- [ ] Next.js 16 + TypeScript + Tailwind CSS 4 项目搭建
- [ ] `react-resizable-panels` 五区域布局（TopBar / ECatalog / Viewport / Properties / Terminal）
- [ ] 颜色系统 CSS 变量（`--bg-base: #1e1e1e` 等 VC 4.8 深色工业风）
- [ ] Zustand 5 store 骨架：`sceneStore` / `catalogStore` / `simulationStore` / `agentStore`
- [ ] 目录结构规范建立

**验收**：浏览器显示五区域分割布局，各区域可拖动调整大小。

#### Week 2：eCatalog 面板

- [ ] `CollectionsTree`：@radix-ui/react-collapsible 折叠树
  - 节点：所有模型 / 公共模型（Components + Layouts）/ 我的模型 / 当前打开 / 最近模型
- [ ] `DeviceGrid`：@tanstack/react-virtual 虚拟化两列网格（Mock 50 条设备）
- [ ] `DeviceCard`：缩略图 + 名称，设置 `draggable` 属性
- [ ] `SearchBar`：本地关键词过滤

**验收**：目录树可折叠展开，500 条设备卡片流畅渲染，搜索过滤有效。

#### Week 3：3D Viewport 基础

- [ ] React Three Fiber Canvas（antialias + shadows）
- [ ] `GridFloor`：50m × 30m，1m 间距网格
- [ ] `OrbitControls`：旋转 / 平移 / 缩放
- [ ] 环境光 + 点光源配置
- [ ] Mock GLB 加载（Box 几何体占位）
- [ ] `DeviceInstance`：位置 / 旋转 / 选中高亮（emissive）
- [ ] 拖拽入场：`DeviceCard` drag → Canvas `onDrop` → Raycasting 地板坐标

**验收**：从 eCatalog 拖拽设备放入 3D 场景，点击设备高亮。

#### Week 4：属性面板 + 仿真控制条

- [ ] `CoordinateWidget`：X/Y/Z + Rx/Ry/Rz，世界/父系/物体坐标系切换
- [ ] `DefaultTab`：PropRowText / PropRowNumber / PropRowSelect
  - conveyor：ConveyorLength / Width / Height / Speed / LiftOffset
  - lift：nodeName / carrierNodeName
  - robot / storage：id / type / nodeName
- [ ] `SimulationTab`：
  - conveyor：StartOffset / EndOffset
  - robot：speed + 关节折叠列表（6 轴，展开显示 axis / limit）
  - lift：rootAxis / carrierAxis / rootRange / carrierRange / speed
  - storage：货格卡片网格，XYZ 可编辑，支持增删
- [ ] `SimulationBar` 浮层：▶ ⏸ ⏹ / 时间显示 / 速度倍率下拉

**验收**：点击不同类型设备，属性面板正确切换字段，修改值实时更新 store。

#### Week 5：AI 聊天 + 终端面板 + 整体联调

- [ ] `AIChatPanel`：MessageList + StreamMessage（RAF 打字机）+ ChatInput（自动增高）
- [ ] `useTypewriter`：batchSize=2，增量续打，IntersectionObserver 可见性检测，skipAnimation
- [ ] `useAgentStream`：Fetch + ReadableStream，SSE 行缓冲解析
- [ ] Mock SSE：setTimeout 模拟流式输出，验证打字机效果
- [ ] `TerminalPanel`：ansi-to-html 着色，自动滚底，Mock 仿真日志输出
- [ ] 整体联调：五区域响应式 + store 数据流 + 拖拽→属性→坐标更新

**验收（M1 里程碑）**：完整前端可交互演示，Mock 数据驱动全流程。

---

### Phase 2：数据库部署 + 数据迁移（Week 6 – Week 8）

> **目标**：Docker 环境就绪，种子数据写入，前端切换真实 API。

#### Week 6：Docker 环境 + PostgreSQL

- [ ] `docker-compose.yml`：PostgreSQL + MongoDB + Redis + MinIO + Nginx
- [ ] Alembic 迁移脚本：所有 PG 表（见 4.1 章节）
- [ ] `pg_trgm` 扩展，全文搜索索引，`updated_at` 触发器

**验收**：`docker-compose up` 一键启动，`alembic upgrade head` 无报错。

#### Week 7：MongoDB + MinIO + 种子数据

- [ ] MongoDB 索引创建脚本（device_specs / scenes / layout_templates）
- [ ] MinIO Bucket 创建（models / thumbnails / exports）
- [ ] `seed_devices.py`：4 类设备写入 PG + MongoDB（PG UUID 与 MongoDB `_id` 保持一致）
- [ ] `scene.json` + 设备配置文件（smart_storage_1.json 等）迁移到 MongoDB `layout_templates`
- [ ] 设备 GLB/URDF 文件上传 MinIO

**验收**：MongoDB Compass 能看到 4 条 device_specs，MinIO 控制台能看到模型文件。

#### Week 8：前端切换真实 API

- [ ] FastAPI 骨架：`GET /api/catalog`，`GET /api/catalog/{id}/model`（预签名 URL）
- [ ] `GET /api/projects/{id}/scene`，`PATCH /api/projects/{id}/scene/devices`
- [ ] 前端 catalogStore + sceneStore 从 Mock 切换为真实 API
- [ ] GLB 文件通过 MinIO 预签名 URL 真实加载

**验收（M2 里程碑）**：真实 GLB 模型显示，属性修改持久化，刷新页面数据保留。

---

### Phase 3：后端核心实现（Week 9 – Week 13）

> **目标**：完成全部 REST API、WebSocket 协同、布局实例化。

#### Week 9：认证 + 项目管理

- [ ] JWT 登录注册接口
- [ ] 依赖注入：`get_current_user` / `require_editor`
- [ ] 项目 CRUD + 成员权限管理

**验收**：Postman 完成注册登录，带 JWT 访问项目接口。

#### Week 10：场景管理 API

- [ ] 场景 CRUD：GET / PATCH（JSON Patch + version 乐观锁）/ POST devices / PATCH device / DELETE
- [ ] Connection CRUD

**验收**：拖拽设备入场后 MongoDB 对应文档 devices 数组新增记录。

#### Week 11：WebSocket 场景同步

- [ ] `ConnectionManager`：project_id → {user_id: WebSocket} 映射
- [ ] WS `/ws/scenes/{project_id}`
- [ ] 场景修改自动广播，Redis 维护在线状态

**验收**：两窗口打开同一项目，一边移动设备，另一边实时同步。

#### Week 12：布局加载 + 文件服务

- [ ] `instantiate_layout` 服务（configFile 三种引用格式解析，param_overrides 深合并）
- [ ] `POST /api/projects/{id}/scene/load-layout`
- [ ] 文件上传/下载/导出 API

**验收**：拖入「智能仓储流水线」布局，6 个设备和 5 条连接自动生成。

#### Week 13：eCatalog 完整 API + 联调

- [ ] eCatalog 分页搜索（Redis 缓存）
- [ ] `GET /api/device-specs/{category}` → 前端属性面板动态渲染用
- [ ] 布局目录接口
- [ ] 前端 Mock 数据全部移除

**验收（M3 里程碑）**：完整流程——搜索→拖放→修改→布局加载→多人协同。

---

### Phase 4：AI Agent 层实现（Week 14 – Week 16）

> **目标**：LangGraph Agent → SimPlan → SimPy → Terminal 全链路打通。

#### Week 14：Agent 骨架（最关键，补足缺口）

- [ ] `SimAgentState` TypedDict 定义（15 个字段）
- [ ] 5 个 `@tool` 函数编写并验证（单独可调用）
- [ ] `llm.bind_tools(tools)` → `orchestrator_node`
- [ ] `ToolNode(tools)` 接入 StateGraph
- [ ] 条件边：`tools_condition`（ReAct 循环）
- [ ] `MemorySaver` + `thread_id` + `interrupt_before=["clarifier"]`
- [ ] **最小可跑通验证**：Level 1 输入「跑一下仿真」→ 图完整执行 → 打印所有工具调用结果

**验收**：命令行执行 `graph.invoke()`，看到 ReAct 循环：read_scene_config → analyze_topology → select_device_algorithm 依次调用。

#### Week 15：Plan Generator + SSE 接入

- [ ] `plan_generator_node`：`structured_output → SimPlanSchema`
- [ ] `plan_validator_node`：参数范围 + 拓扑死锁检测
- [ ] `route_after_validation` 条件边（通过/重试/超限）
- [ ] `clarifier_node`：interrupt 中断 + 用户回答恢复
- [ ] `POST /api/agent/sessions/{id}/messages` SSE 接口
- [ ] `astream_events` 过滤：token / patch / warning / done
- [ ] 前端 AI 聊天接入真实 SSE，打字机效果联调

**验收**：输入「传送带 400mm/s，跑 30 分钟」，聊天面板流式显示 SimPlan 摘要。

#### Week 16：SimPy 执行层 + Terminal 输出

- [ ] `WorkshopSimulation` 类：接收 SimPlan，构建 SimPy 进程
- [ ] `lift_xy_trajectory` 算法对接 `keyPoints.transfer_board`
- [ ] 信号事件系统：`simpy.Event` 实现协调规则
- [ ] ANSI 颜色日志三阶段输出（Agent 调度 / 运行 / 统计）
- [ ] Celery 任务 + Redis Pub/Sub
- [ ] WS `/ws/simulation/{project_id}` 日志 + 帧数据
- [ ] 前端 3D 设备节点动画（载台 carrier 节点根据帧数据移动）

**验收（M4 里程碑）**：点击播放，Terminal 实时滚动 SimPy 日志，3D 场景升降台动态移动。

---

### Phase 5：完善 + 测试 + 部署（Week 17）

> **目标**：端到端集成测试，性能达标，Docker 生产配置。

#### Week 17：集成测试 + 优化 + 部署

- [ ] 端到端流程测试：注册 → 创建项目 → 加载布局 → 修改参数 → AI 仿真 → Terminal 统计
- [ ] 3D 渲染性能：Instanced Mesh，目标 100 设备 60fps
- [ ] Agent 响应时间：首 token < 2s，SimPlan 生成 < 10s
- [ ] WebSocket 重连机制
- [ ] Docker 生产配置（Nginx 反代、MinIO 持久化卷）
- [ ] FastAPI `/docs` API 文档
- [ ] 前端错误边界 + 加载状态兜底

**验收（M5 里程碑）**：完整演示流程，端到端无报错，性能指标达标。

---

## 8. 技术风险与应对

| 风险 | 等级 | 应对策略 |
|---|---|---|
| 大场景 R3F 帧率下降 | 高 | Instanced Mesh + 视锥剔除 + LOD，100+ 设备启用 Web Worker |
| LLM 生成 SimPlan 不符规范 | 高 | Guardian 节点 JSON Schema 强制校验，失败最多重试 3 次 |
| URDF 在 Three.js 加载兼容 | 中 | `urdf-loader` 已在依赖中，keyPoints `nodeName` 用 `getObjectByName` 查找 |
| SimPy + Celery 与 FastAPI 异步边界 | 中 | Celery Worker 用 `asyncio.run` 封装，Redis Pub/Sub 跨进程通信 |
| MongoDB 场景并发写冲突 | 中 | `version` 乐观锁，客户端 409 后重新 fetch 再提交 |
| Agent Week 14 缺口（最关键）| 高 | Week 14 必须完成图骨架最小可跑通，不能跳过直接做 Plan Generator |

---

## 9. 完整依赖清单

### 9.1 前端 package.json（基于现有版本）

```json
{
  "dependencies": {
    "next": "16.1.6",
    "react": "19.2.3",
    "react-dom": "19.2.3",
    "@react-three/fiber": "^9.5.0",
    "@react-three/drei": "^10.7.7",
    "@react-three/postprocessing": "^3.0.4",
    "three": "^0.182.0",
    "@types/three": "^0.182.0",
    "zustand": "^5.0.11",
    "react-resizable-panels": "^4.5.8",
    "urdf-loader": "^0.12.6",
    "xacro-parser": "^0.3.11",
    "lucide-react": "^0.563.0",
    "tailwind-merge": "^3.4.0",
    "clsx": "^2.1.1",
    "class-variance-authority": "^0.7.1",
    "@tanstack/react-virtual": "^3.13.0",
    "@radix-ui/react-tabs": "latest",
    "@radix-ui/react-collapsible": "latest",
    "@radix-ui/react-context-menu": "latest",
    "@radix-ui/react-scroll-area": "latest",
    "@radix-ui/react-select": "latest",
    "@radix-ui/react-checkbox": "latest",
    "ansi-to-html": "latest"
  }
}
```

### 9.2 后端 requirements.txt

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
python-multipart==0.0.9
sqlalchemy[asyncio]==2.0.35
asyncpg==0.29.0
motor==3.5.0
redis[hiredis]==5.0.8
alembic==1.13.0
pydantic==2.9.0
pydantic-settings==2.5.0
langgraph==0.2.35
langchain-core==0.3.15
litellm==1.50.0
jsonschema==4.23.0
celery==5.4.0
simpy==4.1.1
minio==7.2.9
pyjwt==2.9.0
bcrypt==4.2.0
structlog==24.4.0
httpx==0.27.0
orjson==3.10.7
python-dotenv==1.0.1
```

---

## 里程碑汇总

| 里程碑 | 时间节点 | 核心产出 | 关键指标 |
|---|---|---|---|
| M1 前端界面可演示 | Week 5 末 | 全部 UI 组件，Mock 数据驱动 | 5 个面板交互正常，打字机效果流畅 |
| M2 数据库就绪 | Week 8 末 | Docker 环境，种子数据，前端接真实 API | GLB 真实加载，场景数据持久化 |
| M3 后端 API 完整 | Week 13 末 | 全部 REST + WebSocket，布局实例化 | 多人协同同步，布局一键加载 |
| M4 AI 仿真全链路 | Week 16 末 | Agent → SimPlan → SimPy → Terminal | Level 1-3 输入可仿真，Terminal 实时日志 |
| M5 生产就绪 | Week 17 末 | 集成测试，Docker 生产配置 | 100 设备 60fps，首 token < 2s |
