# 数据库架构设计

> PostgreSQL + MongoDB + Redis + MinIO
> 四层分工 · 索引与文档分离

---

## 📋 数据库分工原则

```
PostgreSQL   ← 目录索引层（用户/项目/权限/设备目录/布局目录）
               所有可被 WHERE/JOIN/全文索引的字段

MongoDB      ← 文档存储层
               scenes：场景完整文档（设备实例嵌套，Schema 可变）
               device_specs：设备参数规范模板
               layout_templates：预设布局方案
               agent_messages：Agent 对话消息

Redis        ← 运行时状态
               WebSocket 在线状态
               仿真帧缓冲
               搜索缓存
               Agent Token 缓冲

MinIO        ← 文件存储
               GLB/URDF 模型文件
               缩略图
               导出文件
```

---

## 🗄️ PostgreSQL Schema

### 核心表结构

```sql
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
    scene_doc_id   VARCHAR(36),         -- MongoDB _id
    thumbnail_key  VARCHAR(500),        -- MinIO 路径
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

-- 设备目录（eCatalog 索引，参数规范在 MongoDB）
CREATE TABLE device_catalog (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    device_type     VARCHAR(50) NOT NULL 
                    CHECK (device_type IN ('conveyor','robot','lift','storage')),
    manufacturer    VARCHAR(100),
    model_format    VARCHAR(10) NOT NULL DEFAULT 'glb' 
                    CHECK (model_format IN ('glb','urdf')),
    model_file_key  VARCHAR(500) NOT NULL,   -- MinIO 路径
    thumbnail_key   VARCHAR(500),
    tags            TEXT[] DEFAULT '{}',
    is_public       BOOLEAN DEFAULT TRUE,
    spec_doc_id     VARCHAR(36),             -- MongoDB device_specs._id
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 布局目录（eCatalog 布局文件夹）
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
```

### 索引策略

```sql
-- 全文搜索索引
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE INDEX idx_catalog_name_trgm ON device_catalog USING GIN(name gin_trgm_ops);
CREATE INDEX idx_layout_name_trgm ON layout_catalog USING GIN(name gin_trgm_ops);

-- 标签索引
CREATE INDEX idx_catalog_tags ON device_catalog USING GIN(tags);
CREATE INDEX idx_layout_tags ON layout_catalog USING GIN(tags);

-- 常规索引
CREATE INDEX idx_projects_owner ON projects(owner_id);
CREATE INDEX idx_catalog_type ON device_catalog(device_type);
CREATE INDEX idx_sim_runs_project ON simulation_runs(project_id);
```

---

## 📄 MongoDB Collections

### 1. device_specs（设备参数规范）

与 PG device_catalog 1:1 对应，存储完整参数模板：

```javascript
{
  _id: "uuid-same-as-pg-device-catalog-id",
  device_type: "lift",
  name: "Prorunner mk5-XL",
  manufacturer: "Qimarox",
  
  // 默认参数初始值（对应前端"默认"Tab）
  default_params: {
    id: "",
    type: "lift",
    nodeName: "",
    carrierNodeName: "Carrier_00"
  },
  
  // 仿真参数初始值（对应前端"仿真"Tab）
  simulation_params: {
    speed: 0.5,
    motion: {
      rootAxis: "x",
      carrierAxis: "y",
      rootRange: { min: -4.142, max: 0.858 },
      carrierRange: { min: 0.185, max: 3.160 }
    }
  },
  
  // 参数约束（供 Agent Guardian 校验）
  constraints: {
    speed: { min: 0.05, max: 2.0, unit: "m/s" }
  },
  
  created_at: ISODate("2026-04-15T00:00:00Z")
}
```

### 2. scenes（场景文档）

与 PG projects 1:1 对应，存储完整场景：

```javascript
{
  _id: "project_uuid",
  version: 42,             // 乐观锁
  name: "车间 A 布局",
  
  floor: {
    width: 50.0,
    depth: 30.0,
    grid_size: 1.0
  },
  
  devices: [
    {
      instance_id: "inst-uuid",
      catalog_id: "device-catalog-uuid",
      layout_device_id: "conveyor_1",    // 布局内部 ID
      device_type: "conveyor",
      model_format: "glb",
      
      transform: {
        position: [10.5, 0.0, 5.0],
        rotation: [0.0, 1.5708, 0.0],
        scale: [1.0, 1.0, 1.0]
      },
      
      default_params: { /* 用户在默认 Tab 编辑的值 */ },
      simulation_params: { /* 用户在仿真 Tab 编辑的值 */ },
      
      process_config: {
        behaviors: [{ type: "transport", ... }],
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
      type: "material_flow"
    }
  ],
  
  simulation_config: {
    duration: 3600.0,
    workflow: [ /* 布局工作流 */ ],
    topology: [ /* 布局拓扑关系 */ ]
  },
  
  source_layout_id: "layout-uuid",
  updated_at: ISODate(...)
}
```

### 3. layout_templates（布局模板）

预设布局方案，支持实例化为场景：

```javascript
{
  _id: "layout-uuid",
  version: "1.0",
  name: "智能仓储流水线",
  description: "物料通过传送带传递给升降台...",
  
  devices: [
    {
      id: "conveyor_1",           // 布局内部 ID
      label: "入口传送带",
      configFile: "catalog:uuid-conveyor-standard",   // 引用格式
      param_overrides: {
        default_params: { ConveyorLength: 2000 }
      },
      transform: {
        position: [10.0, 0.0, 0.0],
        rotation: [0.0, 0.0, 0.0],
        scale: [1.0, 1.0, 1.0]
      }
    }
  ],
  
  topology: [
    {
      from: "conveyor_1",
      to: "smart_storage_1",
      relation: "feeds",
      description: "传送带将物料输送至出口"
    }
  ],
  
  workflow: [
    "传送带1将物料输送到出口位置",
    "升降台1移动到传送带出口位置获取物料"
  ],
  
  created_at: ISODate(...)
}
```

### 4. agent_messages（对话消息）

```javascript
{
  _id: "msg-uuid",
  session_id: "session-uuid",
  project_id: "project-uuid",
  role: "assistant",
  content: "已为机械臂-01 配置抓取工艺...",
  applied_patches: [
    {
      instance_id: "...",
      field: "process_config",
      summary: "添加 pick_and_place 行为"
    }
  ],
  created_at: ISODate(...)
}
```

---

## 🔴 Redis 键设计

```
# WebSocket 连接管理
ws:online:{project_id}              SET<user_id>

# 仿真运行状态
sim:state:{project_id}              HASH
    status / sim_time / speed / task_id

# 仿真帧数据
sim:frames:{project_id}             STREAM (限 1000 条)

# eCatalog 搜索缓存
catalog:search:{md5(query)}         STRING (JSON) TTL:300s

# 场景乐观锁
scene:version:{project_id}          STRING

# Agent 流式 Token 缓冲
agent:stream:{session_id}           LIST<token> TTL:600s
```

---

## 📦 MinIO Bucket 结构

```
models/
├── conveyor/{catalog_id}.glb
├── robot/{catalog_id}.urdf
│   └── {catalog_id}/meshes/       # URDF 引用的网格文件
├── lift/{catalog_id}.glb
└── storage/{catalog_id}.glb

thumbnails/
├── catalog/{catalog_id}.jpg       # 设备预览图 240×240
└── projects/{project_id}.jpg      # 项目缩略图 480×270

exports/                           # TTL 24h
└── {project_id}/
    ├── layout_{timestamp}.json
    └── bom_{timestamp}.csv
```

---

## 🔄 数据流示例

### 点击设备读取参数

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

### 布局加载流程

```
用户从 eCatalog 拖入布局
    │
    ▼
POST /api/projects/{id}/scene/load-layout
    │
    ▼
layout_service.instantiate_layout()
    ├── 读取 MongoDB layout_templates
    ├── 解析 configFile 引用（catalog: / file:）
    ├── 合并默认参数 + 布局覆盖
    ├── 从拓扑生成 connections
    └── 写入 MongoDB scenes
    │
    ▼
WebSocket 广播 scene_loaded 事件
    │
    ▼
前端刷新 3D 场景
```

---

## 📊 MongoDB 索引

```javascript
// device_specs
db.device_specs.createIndex({ "device_type": 1 });
db.device_specs.createIndex({ "manufacturer": 1 });

// scenes
db.scenes.createIndex({ "_id": 1 });
db.scenes.createIndex({ "devices.instance_id": 1 });
db.scenes.createIndex({ "devices.device_type": 1 });
db.scenes.createIndex({ "source_layout_id": 1 });
db.scenes.createIndex({ "updated_at": -1 });

// layout_templates
db.layout_templates.createIndex({ "name": "text", "description": "text" });
db.layout_templates.createIndex({ "devices.id": 1 });

// agent_messages
db.agent_messages.createIndex({ "session_id": 1, "created_at": 1 });
db.agent_messages.createIndex({ "project_id": 1, "created_at": -1 });
```

---

## 🚀 初始化脚本

### Alembic 迁移

```bash
cd backend
alembic init migrations
alembic revision --autogenerate -m "initial_schema"
alembic upgrade head
```

### 种子数据

```python
# scripts/seed_devices.py
# 4 类设备写入 PG + MongoDB
# PG UUID 与 MongoDB _id 保持一致
```

---

## 📖 详细文档

- [数据库构建方案](database_construction_plan.md) - 完整 SQL/Schema
- [布局模板补充](database_layout_supplement.md) - 布局实例化逻辑

---

## 🔗 相关资源

- **PostgreSQL**: https://www.postgresql.org/
- **MongoDB**: https://www.mongodb.com/
- **Redis**: https://redis.io/
- **MinIO**: https://min.io/
