# 数据库构建方案

> 工业三维可视化平台 · 四类设备（传送带 / 机械臂 / 升降台 / 仓储柜）
> PostgreSQL + MongoDB + Redis + MinIO

---

## 一、整体分工原则

```
PostgreSQL   目录索引层   ─── 设备名称、类型、文件引用、搜索索引、用户/项目/权限
MongoDB      文档存储层   ─── 设备实例完整参数（default + simulation）、场景文档
Redis        运行时状态   ─── WebSocket 在线状态、仿真帧缓冲、搜索缓存
MinIO        文件存储层   ─── URDF/GLB 模型文件、缩略图
```

**核心设计原则：** PostgreSQL 只存能用于 `WHERE` / `JOIN` / 全文索引的字段。所有嵌套、可变 Schema 的参数（如机械臂关节定义、仓储货格坐标）全部存 MongoDB，两边通过相同的 UUID 关联。

---

## 二、PostgreSQL 完整 Schema

### 2.1 执行脚本（按顺序运行）

```sql
-- ════════════════════════════════════════════════
-- 0. 扩展
-- ════════════════════════════════════════════════
CREATE EXTENSION IF NOT EXISTS "pgcrypto";     -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";      -- 模糊搜索索引


-- ════════════════════════════════════════════════
-- 1. 用户
-- ════════════════════════════════════════════════
CREATE TABLE users (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    email         VARCHAR(255) UNIQUE NOT NULL,
    name          VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active     BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ════════════════════════════════════════════════
-- 2. 项目
-- ════════════════════════════════════════════════
CREATE TABLE projects (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name           VARCHAR(255) NOT NULL,
    description    TEXT,
    owner_id       UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- MongoDB 场景文档 _id（与 project.id 字符串相同，方便关联）
    scene_doc_id   VARCHAR(36),
    thumbnail_key  VARCHAR(500),         -- MinIO: thumbnails/proj/{id}.jpg
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_projects_owner    ON projects(owner_id);
CREATE INDEX idx_projects_updated  ON projects(updated_at DESC);


-- ════════════════════════════════════════════════
-- 3. 项目成员权限
-- ════════════════════════════════════════════════
CREATE TABLE project_members (
    project_id  UUID        NOT NULL REFERENCES projects(id)  ON DELETE CASCADE,
    user_id     UUID        NOT NULL REFERENCES users(id)     ON DELETE CASCADE,
    role        VARCHAR(20) NOT NULL CHECK (role IN ('OWNER', 'EDITOR', 'VIEWER')),
    joined_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (project_id, user_id)
);

CREATE INDEX idx_members_user ON project_members(user_id);


-- ════════════════════════════════════════════════
-- 4. 设备目录（eCatalog 索引层）
-- ════════════════════════════════════════════════
-- 说明：
--   此表只存可被索引、搜索、过滤的字段。
--   设备的完整参数规范（default_schema / simulation_schema）
--   存在 MongoDB 的 device_specs 集合里，通过 id 关联。
-- ════════════════════════════════════════════════
CREATE TABLE device_catalog (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,

    -- 设备类型：与 JSON 规范 key 对应
    device_type     VARCHAR(50)  NOT NULL
                    CHECK (device_type IN ('conveyor', 'robot', 'lift', 'storage')),

    manufacturer    VARCHAR(100),
    model_version   VARCHAR(50),

    -- 模型文件引用（MinIO 路径）
    -- model_format: 'glb' 用于传送带/升降台/仓储柜，'urdf' 用于机械臂
    model_format    VARCHAR(10)  NOT NULL DEFAULT 'glb'
                    CHECK (model_format IN ('glb', 'urdf')),
    model_file_key  VARCHAR(500) NOT NULL,   -- models/{device_type}/{id}.glb 或 .urdf
    thumbnail_key   VARCHAR(500),            -- thumbnails/catalog/{id}.jpg

    -- 搜索字段
    tags            TEXT[]  NOT NULL DEFAULT '{}',
    is_public       BOOLEAN NOT NULL DEFAULT TRUE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,

    -- 关联 MongoDB device_specs 集合的文档 _id（与本表 id 相同）
    spec_doc_id     VARCHAR(36),

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_catalog_type        ON device_catalog(device_type);
CREATE INDEX idx_catalog_mfr         ON device_catalog(manufacturer);
CREATE INDEX idx_catalog_active      ON device_catalog(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_catalog_tags        ON device_catalog USING GIN(tags);
-- 全文搜索（中英文名称模糊匹配）
CREATE INDEX idx_catalog_name_trgm   ON device_catalog USING GIN(name gin_trgm_ops);


-- ════════════════════════════════════════════════
-- 5. Agent 会话（元数据，消息明细存 MongoDB）
-- ════════════════════════════════════════════════
CREATE TABLE agent_sessions (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id     UUID        NOT NULL REFERENCES users(id),
    title       VARCHAR(255),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_sessions_project ON agent_sessions(project_id);


-- ════════════════════════════════════════════════
-- 6. 仿真任务记录
-- ════════════════════════════════════════════════
CREATE TABLE simulation_runs (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id   UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    started_by   UUID        NOT NULL REFERENCES users(id),
    celery_task_id VARCHAR(255),
    status       VARCHAR(20) NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'running', 'done', 'failed', 'cancelled')),
    duration     FLOAT,                   -- 仿真时长（秒）
    speed        FLOAT       DEFAULT 1.0, -- 速度倍率
    -- 仿真完成后的统计摘要（JSON 摘要，详细数据存 MongoDB）
    stats_summary JSONB,
    started_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at  TIMESTAMPTZ
);

CREATE INDEX idx_sim_runs_project ON simulation_runs(project_id);
CREATE INDEX idx_sim_runs_status  ON simulation_runs(status);


-- ════════════════════════════════════════════════
-- 7. 触发器：自动更新 updated_at
-- ════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_updated_at_projects
    BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER set_updated_at_catalog
    BEFORE UPDATE ON device_catalog
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER set_updated_at_agent_sessions
    BEFORE UPDATE ON agent_sessions
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
```

---

## 三、MongoDB 文档结构

### 3.1 Collection: `device_specs`（设备参数规范，与 PG device_catalog 1:1）

```javascript
// 此集合定义每个具体设备型号的默认参数初始值和仿真参数初始值
// 当用户从 eCatalog 拖入设备时，以此为模板创建 DeviceInstance

// ── 传送带示例 ──────────────────────────────────
{
  _id: "uuid-same-as-pg-device-catalog-id",
  device_type: "conveyor",
  name: "Standard Belt Conveyor",
  manufacturer: "Generic",

  // 默认参数初始值（对应前端"默认"Tab）
  default_params: {
    id: "",                    // 实例化时由前端生成
    type: "conveyor",
    nodeName: "",              // 实例化时由用户命名
    ConveyorLength: 1000,      // mm
    ConveyorWidth: 600,        // mm
    ConveyorHeight: 800,       // mm
    ConveyorSpeed: 200,        // mm/s
    liftoffset: 0              // mm
  },

  // 仿真参数初始值（对应前端"仿真"Tab）
  simulation_params: {
    conveyorStartOffset: 0,    // mm
    conveyorEndOffset: 0       // mm
  },

  // 参数约束（供 Agent 校验和 Guardian 使用）
  constraints: {
    ConveyorSpeed: { min: 50, max: 2000, unit: "mm/s" },
    ConveyorLength: { min: 100, max: 10000, unit: "mm" },
    ConveyorWidth:  { min: 100, max: 3000, unit: "mm" },
    ConveyorHeight: { min: 200, max: 2000, unit: "mm" }
  },

  created_at: ISODate("2026-04-15T00:00:00Z")
}


// ── 机械臂示例 ──────────────────────────────────
{
  _id: "uuid-robot-fanuc-m10ia",
  device_type: "robot",
  name: "Fanuc M-10iA",
  manufacturer: "Fanuc",

  default_params: {
    id: "",
    type: "robot",
    nodeName: ""
  },

  simulation_params: {
    speed: 1.5,                // rad/s，末端最大速度
    joints: [
      {
        name: "joint_1",
        nodeName: "Link1_00In",
        type: "revolute",
        axis: { x: 0, y: 1, z: 0 },
        limit: { lower: -3.14159, upper: 3.14159 }
      },
      {
        name: "joint_2",
        nodeName: "Link2_00Jn",
        type: "revolute",
        axis: { x: 0, y: 0, z: 1 },
        limit: { lower: -1.5708, upper: 2.3562 }
      },
      {
        name: "joint_3",
        nodeName: "Link3_00Kn",
        type: "revolute",
        axis: { x: 0, y: 0, z: 1 },
        limit: { lower: -1.5708, upper: 2.3562 }
      },
      {
        name: "joint_4",
        nodeName: "Link4_00Ln",
        type: "revolute",
        axis: { x: 0, y: 0, z: 1 },
        limit: { lower: -1.5708, upper: 2.3562 }
      },
      {
        name: "joint_5",
        nodeName: "Link5_00Mn",
        type: "revolute",
        axis: { x: 1, y: 0, z: 0 },
        limit: { lower: -1.5708, upper: 2.3562 }
      },
      {
        name: "joint_6",
        nodeName: "Link6_00Nn",
        type: "revolute",
        axis: { x: 0, y: 1, z: 0 },
        limit: { lower: -1.5708, upper: 2.3562 }
      }
    ]
  },

  constraints: {
    speed: { min: 0.1, max: 10.0, unit: "rad/s" }
  },

  created_at: ISODate("2026-04-15T00:00:00Z")
}


// ── 升降台示例 ──────────────────────────────────
{
  _id: "uuid-lift-prorunner-mk5",
  device_type: "lift",
  name: "Prorunner mk5-XL",
  manufacturer: "Qimarox",

  default_params: {
    id: "",
    type: "lift",
    nodeName: "",
    carrierNodeName: "Carrier_00"
  },

  simulation_params: {
    speed: 0.5,                  // m/s
    motion: {
      rootAxis: "x",             // 横向移动轴
      carrierAxis: "y",          // 纵向（升降）轴
      rootRange:    { min: -4.142, max: 0.858 },   // m
      carrierRange: { min:  0.185, max: 3.160 }    // m
    }
  },

  constraints: {
    speed: { min: 0.05, max: 2.0, unit: "m/s" }
  },

  created_at: ISODate("2026-04-15T00:00:00Z")
}


// ── 仓储柜示例 ──────────────────────────────────
{
  _id: "uuid-storage-rack-01",
  device_type: "storage",
  name: "Smart Storage Rack 3x4",
  manufacturer: "Generic",

  default_params: {
    id: "",
    type: "storage",
    nodeName: ""
  },

  simulation_params: {
    cells: [
      { id: "A1", position: { x: -1.020, y: 1.595, z: 0.000 } },
      { id: "A2", position: { x: -1.020, y: 2.195, z: 0.000 } },
      { id: "A3", position: { x: -2.040, y: 2.195, z: 0.000 } },
      { id: "B1", position: { x:  0.000, y: 1.595, z: 0.000 } },
      { id: "B2", position: { x:  0.000, y: 2.195, z: 0.000 } },
      { id: "B3", position: { x:  1.020, y: 2.195, z: 0.000 } }
    ]
  },

  constraints: {
    max_cells: 100
  },

  created_at: ISODate("2026-04-15T00:00:00Z")
}
```

---

### 3.2 Collection: `scenes`（场景文档，与 PG projects 1:1）

```javascript
{
  _id: "uuid-same-as-pg-project-id",
  version: 0,               // 乐观锁：每次写入 +1，冲突检测用
  name: "车间 A 布局",

  // 地板配置
  floor: {
    width: 50.0,            // m
    depth: 30.0,            // m
    grid_size: 1.0          // m
  },

  // 设备实例列表（每个实例是从 device_specs 克隆后修改的）
  devices: [

    // ── 传送带实例 ──
    {
      instance_id: "inst-uuid-001",        // 场景内唯一 ID（前端生成）
      catalog_id:  "uuid-conveyor-belt",   // 关联 PG device_catalog.id
      device_type: "conveyor",             // 冗余，避免 JOIN
      model_format: "glb",

      // 场景内位姿
      transform: {
        position: [10.5, 0.0, 5.0],        // [x, y, z] 米
        rotation: [0.0, 1.5708, 0.0],      // Euler rad [rx, ry, rz]
        scale:    [1.0, 1.0, 1.0]
      },

      // 默认参数（用户在属性面板"默认"Tab 编辑）
      default_params: {
        id: "inst-uuid-001",
        type: "conveyor",
        nodeName: "InputConveyor-01",
        ConveyorLength: 2000,
        ConveyorWidth: 600,
        ConveyorHeight: 800,
        ConveyorSpeed: 300,
        liftoffset: 0
      },

      // 仿真参数（用户在属性面板"仿真"Tab 编辑）
      simulation_params: {
        conveyorStartOffset: 50,
        conveyorEndOffset: 50
      },

      // Agent 生成的工艺行为配置
      process_config: {
        behaviors: [
          {
            type: "transport",
            direction: "forward",
            cycle_time: null          // 由速度自动计算
          }
        ],
        states: ["idle", "running", "fault"],
        signals: {
          input:  ["start", "part_ready"],
          output: ["part_arrived", "fault"]
        }
      },

      visible: true,
      locked: false
    },

    // ── 机械臂实例 ──
    {
      instance_id: "inst-uuid-002",
      catalog_id:  "uuid-robot-fanuc-m10ia",
      device_type: "robot",
      model_format: "urdf",

      transform: {
        position: [8.0, 0.0, 3.0],
        rotation: [0.0, 0.0, 0.0],
        scale:    [1.0, 1.0, 1.0]
      },

      default_params: {
        id: "inst-uuid-002",
        type: "robot",
        nodeName: "Robot-Fanuc-01"
      },

      simulation_params: {
        speed: 1.2,
        joints: [
          { name: "joint_1", nodeName: "Link1_00In", type: "revolute",
            axis: { x: 0, y: 1, z: 0 }, limit: { lower: -3.14, upper: 3.14 } },
          { name: "joint_2", nodeName: "Link2_00Jn", type: "revolute",
            axis: { x: 0, y: 0, z: 1 }, limit: { lower: -1.57, upper: 2.36 } },
          { name: "joint_3", nodeName: "Link3_00Kn", type: "revolute",
            axis: { x: 0, y: 0, z: 1 }, limit: { lower: -1.57, upper: 2.36 } },
          { name: "joint_4", nodeName: "Link4_00Ln", type: "revolute",
            axis: { x: 0, y: 0, z: 1 }, limit: { lower: -1.57, upper: 2.36 } },
          { name: "joint_5", nodeName: "Link5_00Mn", type: "revolute",
            axis: { x: 1, y: 0, z: 0 }, limit: { lower: -1.57, upper: 2.36 } },
          { name: "joint_6", nodeName: "Link6_00Nn", type: "revolute",
            axis: { x: 0, y: 1, z: 0 }, limit: { lower: -1.57, upper: 2.36 } }
        ]
      },

      process_config: {
        behaviors: [
          {
            type: "pick_and_place",
            source_instance: "inst-uuid-001",   // 从传送带抓取
            target_instance: "inst-uuid-003",   // 放到升降台
            cycle_time: 8.0,                    // 秒，由 Agent 生成
            payload: 5.0                        // kg
          }
        ],
        states: ["idle", "running", "error"],
        signals: {
          input:  ["start", "part_ready_at_conveyor"],
          output: ["pick_done", "place_done", "fault"]
        }
      },

      visible: true,
      locked: false
    },

    // ── 升降台实例 ──
    {
      instance_id: "inst-uuid-003",
      catalog_id:  "uuid-lift-prorunner-mk5",
      device_type: "lift",
      model_format: "glb",

      transform: {
        position: [5.0, 0.0, 3.0],
        rotation: [0.0, 0.0, 0.0],
        scale:    [1.0, 1.0, 1.0]
      },

      default_params: {
        id: "inst-uuid-003",
        type: "lift",
        nodeName: "Lift-01",
        carrierNodeName: "Carrier_00"
      },

      simulation_params: {
        speed: 0.5,
        motion: {
          rootAxis: "x",
          carrierAxis: "y",
          rootRange:    { min: -4.142, max: 0.858 },
          carrierRange: { min:  0.185, max: 3.160 }
        }
      },

      process_config: {
        behaviors: [
          {
            type: "deliver",
            target_cell: "A2",                   // 目标仓储格位
            target_instance: "inst-uuid-004"     // 目标仓储柜
          }
        ],
        states: ["idle", "moving_x", "moving_y", "done", "error"],
        signals: {
          input:  ["carry_request", "cell_target"],
          output: ["carry_done", "fault"]
        }
      },

      visible: true,
      locked: false
    },

    // ── 仓储柜实例 ──
    {
      instance_id: "inst-uuid-004",
      catalog_id:  "uuid-storage-rack-01",
      device_type: "storage",
      model_format: "glb",

      transform: {
        position: [2.0, 0.0, 3.0],
        rotation: [0.0, 0.0, 0.0],
        scale:    [1.0, 1.0, 1.0]
      },

      default_params: {
        id: "inst-uuid-004",
        type: "storage",
        nodeName: "StorageRack-01"
      },

      simulation_params: {
        cells: [
          { id: "A1", position: { x: -1.020, y: 1.595, z: 0.000 } },
          { id: "A2", position: { x: -1.020, y: 2.195, z: 0.000 } },
          { id: "A3", position: { x: -2.040, y: 2.195, z: 0.000 } },
          { id: "B1", position: { x:  0.000, y: 1.595, z: 0.000 } },
          { id: "B2", position: { x:  0.000, y: 2.195, z: 0.000 } }
        ]
      },

      process_config: {
        behaviors: [
          {
            type: "store",
            capacity: 5,         // 货格总数
            occupied: []         // 当前已占格位（仿真时动态更新）
          }
        ],
        states: ["idle", "receiving", "full"],
        signals: {
          input:  ["receive_item"],
          output: ["slot_full", "all_full"]
        }
      },

      visible: true,
      locked: false
    }
  ],

  // 设备间连接（物流流向、信号传递）
  connections: [
    {
      id: "conn-001",
      from_instance: "inst-uuid-001",   // 传送带输出
      to_instance:   "inst-uuid-002",   // 机械臂接收
      type: "material_flow",
      label: "零件流"
    },
    {
      id: "conn-002",
      from_instance: "inst-uuid-002",   // 机械臂输出
      to_instance:   "inst-uuid-003",   // 升降台承接
      type: "material_flow",
      label: "搬运流"
    },
    {
      id: "conn-003",
      from_instance: "inst-uuid-003",   // 升降台输出
      to_instance:   "inst-uuid-004",   // 存入仓储柜
      type: "material_flow",
      label: "入库流"
    }
  ],

  // 仿真配置
  simulation_config: {
    duration: 3600.0,         // 秒
    warm_up: 0.0,
    random_seed: 42,
    speed_multiplier: 1.0
  },

  updated_at: ISODate("2026-04-15T00:00:00Z")
}
```

---

### 3.3 Collection: `agent_messages`（Agent 对话消息）

```javascript
{
  _id: "msg-uuid",
  session_id: "session-uuid",   // 关联 PG agent_sessions.id
  project_id: "project-uuid",
  role: "assistant",            // "user" | "assistant"
  content: "已为机械臂-01 配置抓取工艺...",

  // Agent 操作摘要（仅 assistant 消息）
  applied_patches: [
    {
      instance_id: "inst-uuid-002",
      field: "process_config.behaviors",
      summary: "添加 pick_and_place 行为，节拍 8s"
    }
  ],

  // 各节点中间状态（调试用）
  agent_trace: {
    intent:          { action: "configure_device", target: "Robot-Fanuc-01" },
    device_category: "robot",
    validation_pass: true
  },

  created_at: ISODate("2026-04-15T12:00:00Z")
}
```

---

## 四、Redis 键设计

```
# ── WebSocket 连接状态 ────────────────────────────────────
ws:online:{project_id}              SET<user_id>           在线用户集合
ws:cursor:{project_id}:{user_id}    String (JSON)          TTL:30s  用户光标位置

# ── 仿真运行状态 ──────────────────────────────────────────
sim:state:{project_id}              HASH
    status          "running"/"paused"/"idle"
    sim_time        "1234.5"
    speed           "1.0"
    task_id         "celery-uuid"

sim:frames:{project_id}             STREAM                 仿真帧（限 1000 条）
    sim_time, device_states_json

# ── eCatalog 搜索缓存 ─────────────────────────────────────
catalog:search:{md5(query_string)}  String (JSON)          TTL:300s
catalog:category:list               String (JSON)          TTL:3600s

# ── 场景乐观锁 ────────────────────────────────────────────
scene:version:{project_id}          String                 当前 version 号（与 MongoDB 同步）

# ── Agent 流式 Token 缓冲 ─────────────────────────────────
agent:stream:{session_id}           LIST<token>            TTL:600s
```

---

## 五、MinIO Bucket 结构

```
buckets/
├── models/                        # 设备 3D 模型文件
│   ├── conveyor/
│   │   └── {catalog_id}.glb
│   ├── robot/
│   │   └── {catalog_id}.urdf
│   │   └── {catalog_id}/          # URDF 引用的网格文件目录
│   │       ├── meshes/
│   │       └── textures/
│   ├── lift/
│   │   └── {catalog_id}.glb
│   └── storage/
│       └── {catalog_id}.glb
│
├── thumbnails/                    # 缩略图
│   ├── catalog/
│   │   └── {catalog_id}.jpg       # 设备预览图（240×240）
│   └── projects/
│       └── {project_id}.jpg       # 项目缩略图（480×270）
│
└── exports/                       # 导出文件（临时，TTL 24h）
    └── {project_id}/
        ├── layout_{timestamp}.json
        └── bom_{timestamp}.csv
```

---

## 六、Alembic 迁移初始化脚本

```bash
# 1. 初始化 Alembic
cd backend
alembic init migrations

# 2. 配置 alembic.ini（数据库连接）
# sqlalchemy.url = postgresql+asyncpg://user:pass@localhost/workshop_db

# 3. 生成初始迁移
alembic revision --autogenerate -m "initial_schema"

# 4. 执行迁移
alembic upgrade head
```

```python
# migrations/env.py 关键配置
from models.pg.base import Base
from models.pg.user import User
from models.pg.project import Project
from models.pg.device_catalog import DeviceCatalog
from models.pg.agent_session import AgentSession
from models.pg.simulation_run import SimulationRun

target_metadata = Base.metadata
```

---

## 七、MongoDB 索引创建脚本

```javascript
// 在 MongoDB Shell 或应用启动时执行

// ── device_specs ──
db.device_specs.createIndex({ "device_type": 1 });
db.device_specs.createIndex({ "manufacturer": 1 });

// ── scenes ──
db.scenes.createIndex({ "_id": 1 });                       // 主键（默认）
db.scenes.createIndex({ "devices.instance_id": 1 });       // 按实例 ID 快速定位
db.scenes.createIndex({ "devices.device_type": 1 });       // 按类型筛选设备
db.scenes.createIndex({ "updated_at": -1 });

// ── agent_messages ──
db.agent_messages.createIndex({ "session_id": 1, "created_at": 1 });
db.agent_messages.createIndex({ "project_id": 1, "created_at": -1 });
```

---

## 八、初始种子数据（device_specs + device_catalog）

```python
# scripts/seed_devices.py
# 运行：python scripts/seed_devices.py

import asyncio
from core.database import get_pg_session, get_mongo_db
from models.pg.device_catalog import DeviceCatalog

SEED_DEVICES = [
    # ── 传送带 ──
    {
        "pg": {
            "name": "Standard Belt Conveyor",
            "device_type": "conveyor",
            "manufacturer": "Generic",
            "model_format": "glb",
            "model_file_key": "models/conveyor/standard-belt.glb",
            "thumbnail_key": "thumbnails/catalog/standard-belt.jpg",
            "tags": ["conveyor", "belt", "transport"],
        },
        "mongo_default_params": {
            "id": "", "type": "conveyor", "nodeName": "",
            "ConveyorLength": 1000, "ConveyorWidth": 600,
            "ConveyorHeight": 800, "ConveyorSpeed": 200, "liftoffset": 0
        },
        "mongo_simulation_params": {
            "conveyorStartOffset": 0, "conveyorEndOffset": 0
        },
        "constraints": {
            "ConveyorSpeed": {"min": 50, "max": 2000, "unit": "mm/s"}
        }
    },
    # ── 机械臂 ──
    {
        "pg": {
            "name": "Fanuc M-10iA",
            "device_type": "robot",
            "manufacturer": "Fanuc",
            "model_format": "urdf",
            "model_file_key": "models/robot/fanuc-m10ia.urdf",
            "thumbnail_key": "thumbnails/catalog/fanuc-m10ia.jpg",
            "tags": ["robot", "6axis", "fanuc"],
        },
        "mongo_default_params": {
            "id": "", "type": "robot", "nodeName": ""
        },
        "mongo_simulation_params": {
            "speed": 1.5,
            "joints": [
                {"name":"joint_1","nodeName":"Link1_00In","type":"revolute",
                 "axis":{"x":0,"y":1,"z":0},"limit":{"lower":-3.14,"upper":3.14}},
                {"name":"joint_2","nodeName":"Link2_00Jn","type":"revolute",
                 "axis":{"x":0,"y":0,"z":1},"limit":{"lower":-1.57,"upper":2.36}},
                {"name":"joint_3","nodeName":"Link3_00Kn","type":"revolute",
                 "axis":{"x":0,"y":0,"z":1},"limit":{"lower":-1.57,"upper":2.36}},
                {"name":"joint_4","nodeName":"Link4_00Ln","type":"revolute",
                 "axis":{"x":0,"y":0,"z":1},"limit":{"lower":-1.57,"upper":2.36}},
                {"name":"joint_5","nodeName":"Link5_00Mn","type":"revolute",
                 "axis":{"x":1,"y":0,"z":0},"limit":{"lower":-1.57,"upper":2.36}},
                {"name":"joint_6","nodeName":"Link6_00Nn","type":"revolute",
                 "axis":{"x":0,"y":1,"z":0},"limit":{"lower":-1.57,"upper":2.36}}
            ]
        },
        "constraints": {
            "speed": {"min": 0.1, "max": 10.0, "unit": "rad/s"}
        }
    },
    # ── 升降台 ──
    {
        "pg": {
            "name": "Prorunner mk5-XL",
            "device_type": "lift",
            "manufacturer": "Qimarox",
            "model_format": "glb",
            "model_file_key": "models/lift/prorunner-mk5-xl.glb",
            "thumbnail_key": "thumbnails/catalog/prorunner-mk5.jpg",
            "tags": ["lift", "vertical", "carrier"],
        },
        "mongo_default_params": {
            "id": "", "type": "lift",
            "nodeName": "", "carrierNodeName": "Carrier_00"
        },
        "mongo_simulation_params": {
            "speed": 0.5,
            "motion": {
                "rootAxis": "x", "carrierAxis": "y",
                "rootRange":    {"min": -4.142, "max": 0.858},
                "carrierRange": {"min":  0.185, "max": 3.160}
            }
        },
        "constraints": {
            "speed": {"min": 0.05, "max": 2.0, "unit": "m/s"}
        }
    },
    # ── 仓储柜 ──
    {
        "pg": {
            "name": "Smart Storage Rack 3×4",
            "device_type": "storage",
            "manufacturer": "Generic",
            "model_format": "glb",
            "model_file_key": "models/storage/smart-rack-3x4.glb",
            "thumbnail_key": "thumbnails/catalog/smart-rack.jpg",
            "tags": ["storage", "rack", "warehouse"],
        },
        "mongo_default_params": {
            "id": "", "type": "storage", "nodeName": ""
        },
        "mongo_simulation_params": {
            "cells": [
                {"id":"A1","position":{"x":-1.020,"y":1.595,"z":0.000}},
                {"id":"A2","position":{"x":-1.020,"y":2.195,"z":0.000}},
                {"id":"A3","position":{"x":-2.040,"y":2.195,"z":0.000}},
                {"id":"B1","position":{"x": 0.000,"y":1.595,"z":0.000}},
                {"id":"B2","position":{"x": 0.000,"y":2.195,"z":0.000}},
                {"id":"B3","position":{"x": 1.020,"y":2.195,"z":0.000}}
            ]
        },
        "constraints": {
            "max_cells": 100
        }
    },
]

async def seed():
    async with get_pg_session() as session:
        mongo = await get_mongo_db()
        for item in SEED_DEVICES:
            pg_data = item["pg"]
            catalog = DeviceCatalog(**pg_data)
            session.add(catalog)
            await session.flush()   # 获取 id

            # MongoDB device_specs
            await mongo.device_specs.insert_one({
                "_id": str(catalog.id),
                "device_type": pg_data["device_type"],
                "name": pg_data["name"],
                "manufacturer": pg_data["manufacturer"],
                "default_params": item["mongo_default_params"],
                "simulation_params": item["mongo_simulation_params"],
                "constraints": item.get("constraints", {}),
            })
            catalog.spec_doc_id = str(catalog.id)
        await session.commit()
    print("✅ 种子数据写入完成")

asyncio.run(seed())
```
