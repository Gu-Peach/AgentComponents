# 数据库补充方案：布局模板（Layout Templates）

> 在现有 PostgreSQL + MongoDB 方案基础上新增布局层
> 核心概念：布局 = 设备实例引用索引 + 拓扑关系 + 工作流描述

---

## 一、概念层级澄清

```
device_catalog（PG）         ← 设备型号库（类似 VC eCatalog 单个组件）
      │  1:1
device_specs（Mongo）        ← 设备完整参数规范模板

scenes（Mongo）              ← 用户自己搭建的工作场景（实时编辑）
      │  引用
device_instances             ← 场景中每个设备的具体实例

layout_templates（Mongo）    ← 预设布局方案（你 JSON 中的这层）
      │  索引
layout_devices               ← 布局中设备的引用（configFile 对应）
```

**关键区分：**
- `scenes` 是用户正在编辑的"活文档"，设备实例数据完整内嵌
- `layout_templates` 是预定义好的"方案模板"，只存引用索引 + 拓扑 + 工作流
- 用户从 eCatalog 加载一个布局模板时，系统按引用把各设备实例化，写入 `scenes`

---

## 二、PostgreSQL 新增表

```sql
-- ════════════════════════════════════════════════
-- 布局模板索引（eCatalog 中"布局"文件夹的条目）
-- ════════════════════════════════════════════════
CREATE TABLE layout_catalog (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    description     TEXT,

    -- 对应 MongoDB layout_templates._id
    template_doc_id VARCHAR(36) NOT NULL,

    -- eCatalog 展示用
    thumbnail_key   VARCHAR(500),          -- MinIO: thumbnails/layouts/{id}.jpg
    tags            TEXT[]  DEFAULT '{}',
    is_public       BOOLEAN DEFAULT TRUE,
    author_id       UUID    REFERENCES users(id),

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_layout_catalog_tags    ON layout_catalog USING GIN(tags);
CREATE INDEX idx_layout_catalog_name    ON layout_catalog USING GIN(name gin_trgm_ops);
CREATE INDEX idx_layout_catalog_public  ON layout_catalog(is_public) WHERE is_public = TRUE;

CREATE TRIGGER set_updated_at_layout_catalog
    BEFORE UPDATE ON layout_catalog
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
```

**为什么布局模板只在 PG 建一个索引表，主体存 Mongo？**
布局模板的设备列表、拓扑关系、工作流步骤都是嵌套数组，Schema 不固定
（不同布局的设备数量、拓扑边数都不同），用 MongoDB 文档存储更自然，
PG 只承担搜索、筛选、权限等结构化查询。

---

## 三、MongoDB 新增集合

### 3.1 Collection: `layout_templates`

```javascript
// 对应你 JSON 的完整结构，加上数据库所需的元信息

{
  _id: "uuid-same-as-pg-layout-catalog-id",
  version: "1.0",
  name: "智能仓储流水线",
  description: "物料首先通过传送带传递给升降台，升降台将物料传递给仓储柜指定仓储位置。...",

  // ── 设备引用列表 ──────────────────────────────
  // configFile 可以是：
  //   "catalog:{catalog_id}"    → 引用 PG device_catalog 中的设备型号
  //   "spec:{spec_doc_id}"      → 引用 MongoDB device_specs 中的具体规范
  //   "file:devices/xxx.json"   → 引用 MinIO 中的独立 JSON 配置文件（兼容旧格式）
  devices: [
    {
      id: "conveyor_1",           // 布局内部 ID（拓扑引用用）
      label: "入口传送带",
      configFile: "catalog:uuid-conveyor-standard",   // 引用设备目录
      // 布局级别的参数覆盖（可选，覆盖 device_spec 的默认值）
      param_overrides: {
        default_params: {
          ConveyorLength: 2000,
          ConveyorSpeed: 300
        }
      },
      // 布局中该设备的初始位姿
      transform: {
        position: [10.0, 0.0, 0.0],
        rotation: [0.0, 0.0, 0.0],
        scale: [1.0, 1.0, 1.0]
      }
    },
    {
      id: "smart_storage_1",
      label: "入口侧升降台",
      configFile: "catalog:uuid-lift-prorunner-mk5",
      param_overrides: {},
      transform: {
        position: [5.0, 0.0, 0.0],
        rotation: [0.0, 0.0, 0.0],
        scale: [1.0, 1.0, 1.0]
      }
    },
    {
      id: "storage",
      label: "智能仓储柜",
      configFile: "catalog:uuid-storage-rack-01",
      param_overrides: {
        simulation_params: {
          cells: [
            { id: "A1", position: { x: -1.020, y: 1.595, z: 0.000 } },
            { id: "A2", position: { x: -1.020, y: 2.195, z: 0.000 } },
            { id: "A3", position: { x: -2.040, y: 2.195, z: 0.000 } }
          ]
        }
      },
      transform: {
        position: [0.0, 0.0, 0.0],
        rotation: [0.0, 0.0, 0.0],
        scale: [1.0, 1.0, 1.0]
      }
    },
    {
      id: "smart_storage_2",
      label: "出口侧升降台",
      configFile: "catalog:uuid-lift-prorunner-mk5",
      param_overrides: {},
      transform: {
        position: [-5.0, 0.0, 0.0],
        rotation: [0.0, 3.14159, 0.0],
        scale: [1.0, 1.0, 1.0]
      }
    },
    {
      id: "conveyor_2",
      label: "出口传送带",
      configFile: "catalog:uuid-conveyor-standard",
      param_overrides: {
        default_params: {
          ConveyorLength: 1500,
          ConveyorSpeed: 250
        }
      },
      transform: {
        position: [-10.0, 0.0, 0.0],
        rotation: [0.0, 0.0, 0.0],
        scale: [1.0, 1.0, 1.0]
      }
    },
    {
      id: "object",
      label: "物料对象",
      configFile: "file:devices/object.json",       // MinIO 独立文件引用
      param_overrides: {},
      transform: {
        position: [12.0, 0.0, 0.0],
        rotation: [0.0, 0.0, 0.0],
        scale: [1.0, 1.0, 1.0]
      }
    }
  ],

  // ── 拓扑关系 ──────────────────────────────────
  // 描述设备间的物料流和操作关系
  // from/to 引用上方 devices[].id
  topology: [
    {
      from: "conveyor_1",
      to: "smart_storage_1",
      relation: "feeds",
      description: "传送带将物料输送至传送带出口，给升降台获取"
    },
    {
      from: "smart_storage_1",
      to: "storage",
      relation: "manipulates",
      description: "升降台1（智能仓储设备）将物料传递给仓储柜中的空闲位置"
    },
    {
      from: "storage",
      to: "smart_storage_2",
      relation: "manipulates",
      description: "升降台2从仓储柜中获取物料"
    },
    {
      from: "smart_storage_2",
      to: "conveyor_2",
      relation: "manipulates",
      description: "升降台2将物料传递给传送带2"
    },
    {
      from: "conveyor_2",
      to: "end",
      relation: "manipulates",
      description: "末端传送带运输物料到出口"
    }
  ],

  // ── 工作流步骤 ────────────────────────────────
  // 有序的自然语言描述，供 Agent 理解整体工艺逻辑
  // 也用于仿真引擎初始化执行顺序
  workflow: [
    "传送带1将物料输送到出口位置",
    "升降台1移动到传送带出口位置获取物料",
    "升降台1将物料送达仓储柜的指定格子（如A1、A2等）",
    "升降台2移动到仓储柜的指定格子获取物料",
    "升降台2将物料传递给传送带2",
    "传送带2将物料输送到出口"
  ],

  created_at: ISODate("2026-04-15T00:00:00Z"),
  updated_at: ISODate("2026-04-15T00:00:00Z")
}
```

---

### 3.2 布局加载为场景的实例化逻辑（Python 伪代码）

```python
# services/layout_service.py

async def instantiate_layout(
    layout_id: str,
    project_id: str,
) -> SceneDocument:
    """
    将布局模板实例化为可编辑的场景文档。
    调用时机：用户从 eCatalog 拖入一个布局文件。
    """
    mongo = await get_mongo_db()
    template = await mongo.layout_templates.find_one({"_id": layout_id})

    device_instances = []

    for dev_ref in template["devices"]:
        config_file = dev_ref["configFile"]

        # 解析 configFile 引用类型
        if config_file.startswith("catalog:"):
            catalog_id = config_file.split("catalog:")[1]
            spec = await mongo.device_specs.find_one({"_id": catalog_id})

        elif config_file.startswith("file:"):
            file_key = config_file.split("file:")[1]
            # 从 MinIO 读取独立 JSON 配置
            spec = await minio_client.get_json(bucket="models", key=file_key)

        # 合并默认参数 + 布局级覆盖参数
        overrides = dev_ref.get("param_overrides", {})
        default_params = {
            **spec["default_params"],
            **overrides.get("default_params", {}),
            "id": str(uuid4()),           # 生成实例 ID
            "nodeName": dev_ref["label"], # 用布局标签作为初始名称
        }
        simulation_params = {
            **spec["simulation_params"],
            **overrides.get("simulation_params", {}),
        }

        # 从拓扑生成 process_config 骨架
        process_config = build_process_config_from_topology(
            device_id=dev_ref["id"],
            topology=template["topology"],
            workflow=template["workflow"],
        )

        device_instances.append({
            "instance_id": default_params["id"],
            "catalog_id": catalog_id if config_file.startswith("catalog:") else None,
            "layout_device_id": dev_ref["id"],   # 保留布局内部 ID，仿真引擎引用用
            "device_type": spec["device_type"],
            "model_format": spec.get("model_format", "glb"),
            "transform": dev_ref["transform"],
            "default_params": default_params,
            "simulation_params": simulation_params,
            "process_config": process_config,
            "visible": True,
            "locked": False,
        })

    # 从拓扑生成连接关系
    connections = build_connections_from_topology(
        topology=template["topology"],
        device_map={
            d["layout_device_id"]: d["instance_id"]
            for d in device_instances
        }
    )

    # 写入 scenes 集合
    scene = {
        "_id": project_id,
        "version": 0,
        "name": template["name"],
        "floor": {"width": 50.0, "depth": 30.0, "grid_size": 1.0},
        "devices": device_instances,
        "connections": connections,
        "simulation_config": {
            "duration": 3600.0,
            "warm_up": 0.0,
            "random_seed": 42,
            "speed_multiplier": 1.0,
            # 布局工作流注入，供仿真引擎使用
            "workflow": template["workflow"],
            "topology": template["topology"],
        },
        "source_layout_id": layout_id,    # 记录来源布局，便于溯源
        "updated_at": datetime.utcnow(),
    }
    await mongo.scenes.insert_one(scene)
    return scene
```

---

## 四、场景中点击设备→读取参数的数据流

```
用户点击 3D 场景中的设备
          │
          ▼
前端 sceneStore
  selectedId = instance_id
          │
          ▼
PropertiesPanel 渲染
  从 sceneStore.devices 中找到该 instance
  ↓ 本地已有完整的 default_params + simulation_params
  → 直接渲染，无需额外网络请求（场景加载时已全量获取）

# ─── 场景首次加载流程 ─────────────────────────────
GET /api/projects/{id}/scene
          │
          ▼
SceneService.get_scene(project_id)
  → MongoDB scenes.find_one({"_id": project_id})
  → 返回完整 SceneDocument（含所有 devices 的 default_params + simulation_params）
          │
          ▼
前端 sceneStore.devices = response.devices
  → 所有设备参数缓存在 Zustand store 中
  → 点击任意设备时，O(n) 查找即可，无网络延迟
```

---

## 五、MongoDB 索引更新

```javascript
// 新增 layout_templates 集合索引
db.layout_templates.createIndex({ "name": "text", "description": "text" });
db.layout_templates.createIndex({ "devices.id": 1 });

// scenes 集合新增字段索引
db.scenes.createIndex({ "source_layout_id": 1 });              // 按来源布局查询
db.scenes.createIndex({ "devices.layout_device_id": 1 });      // 拓扑引用查找

// 设备实例快速检索（原有，确认存在）
db.scenes.createIndex({ "devices.instance_id": 1 });
db.scenes.createIndex({ "devices.device_type": 1 });
```

---

## 六、eCatalog 目录树更新

在前端 eCatalog 的目录树中，公共模型下分为两个子节点：

```
公共模型
  ├── Components（部件）   → 来源：PG device_catalog
  └── Layouts（布局）      → 来源：PG layout_catalog
```

对应 API：

```
GET /api/catalog?type=device    → 返回 device_catalog 列表（Components 文件夹）
GET /api/catalog?type=layout    → 返回 layout_catalog 列表（Layouts 文件夹）

GET /api/layouts/{id}           → 返回 layout_template 完整 JSON
POST /api/projects/{id}/scene/load-layout
    Body: { layout_id }
    → 调用 instantiate_layout，返回初始化完成的 SceneDocument
```

---

## 七、完整数据流汇总

```
                    ┌─────────────────────────────────────────────┐
                    │              eCatalog Panel                  │
                    │   Components 文件夹   Layouts 文件夹         │
                    └───────┬─────────────────────┬───────────────┘
                            │ 拖单个设备            │ 拖整个布局
                            ▼                      ▼
                   POST /scene/devices    POST /scene/load-layout
                            │                      │
                            │              layout_templates（Mongo）
                            │                      │ 读规范、实例化
                            ▼                      ▼
                   device_specs（Mongo）──→ scenes（Mongo）devices[]
                            │                      │
                            └──────────────────────┘
                                       │
                              GET /projects/{id}/scene
                                       │
                                       ▼
                              前端 sceneStore.devices
                                       │
                            点击设备 → PropertiesPanel
                            直接读本地 store，无额外请求
```
