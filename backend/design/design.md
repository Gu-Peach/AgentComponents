# VC Simulation Backend 设计与校验记录

更新时间：2026-09-07  
当前阶段：基础业务后端 + Phase 1 信号事件投递，不包含 Agent、LLM 调用、自动规划或复杂调度编排。

## 1. 当前实现范围

`backend/` 目前实现的是 VC 风格仿真建模的基础服务层：项目、设备规范、资产元数据、场景文档、接口编译、拓扑派生、仿真运行记录、Redis 运行态缓存，以及 Phase 1 信号事件投递。它的边界是“保存和校验显式建模事实，并验证信号能沿显式连线流动”，不是在本阶段生成智能体行为图或执行复杂调度。

已实现模块：

- FastAPI 应用入口：`app/main.py`
- API 路由：`app/api/projects.py`、`device_specs.py`、`assets.py`、`scenes.py`、`simulation.py`
- SQLAlchemy 模型：`app/db/models.py`
- 仓储层：`app/repositories/sql.py`
- 业务服务：`ProjectService`、`DeviceSpecService`、`AssetService`、`SceneService`、`SimulationService`
- 编译/校验服务：`InterfaceCompiler`、`TopologyBuilder`、`validation.py`
- 运行态存储：`RedisRuntimeStateStore` 与测试用 `InMemoryRuntimeStateStore`
- 信号运行时：`SignalBusRuntime`

## 2. VC 对齐关系

本阶段保留 VC 里“接口分层”的关键建模思想，不把所有接口揉成一个泛化字段：

| 本项目字段 | VC 对应概念 | 作用边界 |
| --- | --- | --- |
| `DeviceSpec.physical_interfaces[]` | `vcSimInterface` / section / field | 真实几何锚点、吸附、装配、抓取、放置、兼容性校验 |
| `DeviceSpec.process_ports[]` | `vcFlow` / `vcConnector` / Transport node | 工艺/物料流端口，可有独立 `local_frame`，表达物料进出、加工、等待和交接位置 |
| `DeviceSpec.signal_ports[]` | `vcSignal` / `vcBooleanSignalMap` | 抽象控制、状态、事件端口；本身不强制具备坐标 |
| `DeviceSpec.interface_bindings[]` | VC 组件内部行为/接口映射 | 声明物理接口、工艺端口、信号端口与 transport behavior 的关联 |
| `SceneDocument.process_edges[]` | 工艺连线 | 用户/前端确认的物料或工艺顺序事实 |
| `SceneDocument.physical_edges[]` | 真实连接/几何对接 | 用户显式连接或由 process edge + binding 编译得到的物理连接事实 |
| `SceneDocument.signal_edges[]` | 信号连接 | 设备信号口之间的静态通讯、互锁、事件投递事实 |
| `TopologyGraph` | 派生运行索引 | 从 DeviceSpec + SceneDocument 编译，供校验、查询、Runtime 使用，不作为手写事实源 |

## 3. 功能级实现矩阵

| 功能 | VC 中的实现方式 | 当前项目实现方式 | API / 服务函数 | 数据结构与存储 |
| --- | --- | --- | --- | --- |
| 项目与场景容器 | VC 由 `vcApplication.Components` 管理当前 layout，组件直接存在于应用文档中 | `ProjectService.create()` 创建项目并自动生成空 `SceneDocument` | `POST /api/projects`、`GET /api/projects/{project_id}/scene` | `projects`、`scenes.current_document` |
| 设备规范导入 | VC 组件能力分散在 component behaviours、properties、connectors、signals 和 sim interfaces 中 | `DeviceSpecService.import_defaults()` 从 `docs/business/SimulationSchema/1.DeviceSpec/**/_1.json` 导入统一 DeviceSpec | `POST /api/device-specs/import-defaults`、`GET /api/device-specs` | `device_specs.document` JSON |
| 资产元数据 | VC 组件/模型资源由本地 library、layout/component 文件引用 | `AssetService` 只保存 Supabase bucket/path/mime/metadata，不在本阶段做二进制上传代理 | `POST /api/assets`、`GET /api/assets/{asset_id}` | `assets` 表；Storage buckets: `models`、`thumbnails`、`uploads`、`exports` |
| 场景实例编辑 | VC 通过 layout 中的 `vcComponent`、节点 transform 和属性表示设备实例 | `SceneService.add_instance/patch_instance/delete_instance()` 维护 `instances[]`，使用 revision 乐观锁 | `/scene/instances` POST/PATCH/DELETE | `scenes.current_document.instances[]`、`scene_events` |
| 工艺边 | VC Process Modeling 中由用户手工配置 product flow / statements；物流端口由 `vcFlow.Connectors` 表达 | `SceneService.create_edge(..., "process")` 保存端口级 `process_edges[]` 并校验 source/target 方向 | `POST /scene/process-edges` | `SceneDocument.process_edges[]` |
| 物理连接边 | VC 中 `vcSimInterface.canConnect/connect` 与 section/frame/field 做吸附、装配和兼容性连接；`vcConnector.Connection` 表达已连端口 | `SceneService.create_edge(..., "physical")` 保存真实物理接口边；`InterfaceCompiler` 可从 process edge + binding 派生 | `POST /scene/physical-edges`、`POST /interfaces/compile` | `SceneDocument.physical_edges[]` |
| 信号连接边 | VC 中 `vcSignal.connect()`、`vcSignal.Connections`、`vcBooleanSignalMap.connect()` 表达信号/端口连接 | `SceneService.create_edge(..., "signal")` 保存信号边，校验方向和值类型；编译器可生成互锁/触发边 | `POST /scene/signal-edges`、`POST /interfaces/compile` | `SceneDocument.signal_edges[]` |
| 拓扑派生 | VC 没有全场景 topology API；需要遍历 `Component -> Behaviour/Flow -> Connector -> Connection` 重建端口图 | `TopologyBuilder.build()` 从 SceneDocument + DeviceSpec 生成 `physical_graph/process_graph/signal_graph/transport_graph` | `POST /topology/rebuild`、`GET /topology/reachability` | `scene_topologies.document` |
| 仿真运行记录 | VC Runtime 运行在应用内部，状态分散在 component behaviour、signals、script tasks 中 | `SimulationService.create_run()` 固化场景版本并初始化 snapshot | `POST /api/projects/{project_id}/simulation-runs` | `simulation_runs`、Redis snapshot |
| 运行态信号/快照 | VC `vcBoolSignal.Value` 保存最新值，`signal()` 触发 `OnSignal/OnSignalTrigger`；脚本可把事件放入任务队列 | `SignalBusRuntime` 沿 `SceneDocument.signal_edges[]` 投递信号，`RedisRuntimeStateStore` 保存 snapshot、latest signal、event stream、device task stream | `/runtime-snapshot` GET/PUT/DELETE、`/signals/{signal_id}/emit` | Redis `runtime:simulation:*`、`stream:simulation:*`；`simulation_events` |

## 4. 数据库设计

Supabase 本地 Postgres 使用 `backend/supabase/migrations/20260906190000_initial_backend_schema.sql` 初始化。当前表：

- `projects`：项目基本信息。
- `assets`：模型、缩略图、上传件、导出件等 Supabase Storage 元数据。
- `device_specs`：设备规范文档，保存 VC 对齐的端口、接口、绑定、行为契约。
- `scenes`：每个项目的当前 `SceneDocument`，含 revision 乐观锁。
- `scene_events`：场景编辑事件流水，用于审计和后续回放。
- `scene_topologies`：由场景文档派生出的 `TopologyGraph` 快照。
- `simulation_runs`：一次仿真运行的元数据和基础场景版本引用。
- `simulation_events`：仿真事件流水，包括信号投递等运行事件。

迁移同时创建 Supabase Storage bucket：`models`、`thumbnails`、`uploads`、`exports`。

## 5. Supabase 与 Redis 边界

Supabase 负责低频、可持久化事实：项目、资产、设备规范、场景文档、场景事件、拓扑快照、仿真运行元数据。Redis 负责高频运行态：运行快照、最新信号值、信号事件流，并通过 TTL 自动释放短期状态。

本地端口已调整为独立 `554xx` 段，避免和仓库中已有 Supabase 项目冲突：

- Supabase API：`http://127.0.0.1:55421`
- Supabase Postgres：`postgresql://postgres:postgres@127.0.0.1:55422/postgres`
- Supabase Studio：`http://127.0.0.1:55423`
- Redis：`redis://:local_redis_pass@127.0.0.1:6380/0`

## 6. API 范围

当前 API 只覆盖基础业务后端：

- `GET /health`：健康检查，返回 `agent_enabled=false`。
- `/api/projects`：创建、列表、读取项目。
- `/api/device-specs`：创建设备规范、导入默认设备、列表、读取。
- `/api/assets`：创建、列表、读取资产元数据。
- `/api/projects/{project_id}/scene`：读取项目当前场景文档。
- `/api/projects/{project_id}/scene/instances`：添加、修改、删除实例。
- `/api/projects/{project_id}/scene/{process|physical|signal}-edges`：管理三类场景边。
- `/api/projects/{project_id}/interfaces/compile`：将 process edge + interface binding 编译为 physical/signal edge，可 dry-run 或 apply。
- `/api/projects/{project_id}/topology/rebuild`：重建派生拓扑图。
- `/api/projects/{project_id}/topology`：读取最新拓扑图。
- `/api/projects/{project_id}/topology/reachability`：查询指定 graph 上的可达性。
- `/api/projects/{project_id}/simulation-runs`：创建仿真运行。
- `/api/simulation-runs/{run_id}`：读取仿真运行及 Redis snapshot/signals。
- `/api/simulation-runs/{run_id}/runtime-snapshot`：读取/写入/清除运行快照。
- `/api/simulation-runs/{run_id}/signals/{signal_id}/emit`：写入 source signal，按 `SceneDocument.signal_edges[]` 投递 target signal，记录 routed event，并生成 pending device task。

核心请求/响应格式：

```json
// POST /api/projects
{ "name": "Pallet sorting line", "description": "optional" }
// response
{ "id": "project_xxx", "name": "Pallet sorting line", "description": "optional" }

// POST /api/projects/{project_id}/scene/instances
{
  "base_revision": 0,
  "spec_id": "conveyor_1",
  "instance_id": "main_conveyor_1",
  "transform": { "position": [0, 0, 0], "rotation_euler": [0, 0, 0], "scale": [1, 1, 1] },
  "param_overrides": {}
}
// mutation response
{ "scene_id": "scene_xxx", "previous_revision": 0, "new_revision": 1, "event_id": "event_xxx", "document": {}, "warnings": [] }

// POST /api/projects/{project_id}/scene/process-edges
{ "base_revision": 1, "edge_id": "proc_1", "source": "conv_1.flow_output", "target": "robot_1.flow_input", "edge_type": "material_flow" }

// POST /api/projects/{project_id}/scene/signal-edges
{
  "base_revision": 2,
  "source": "conv_1.part_ready",
  "target": "robot_1.start_pick",
  "delivery": "event",
  "trigger": "on_rising_edge",
  "transform": { "type": "identity" }
}

// POST /api/projects/{project_id}/interfaces/compile
{ "base_revision": 3, "mode": "dry_run" }
// response contains compiled_physical_edges[], compiled_signal_edges[], warnings[]

// PUT /api/simulation-runs/{run_id}/runtime-snapshot
{ "snapshot": { "clock": 2, "signal_values": { "conv_1.part_ready": true } }, "ttl_seconds": 86400 }

// POST /api/simulation-runs/{run_id}/signals/{signal_id}/emit
{ "value": true, "payload": { "material_id": "part_001" }, "sim_time_s": 1.5, "ttl_seconds": 86400 }
```

异常格式统一为：

```json
{ "error": "SCENE_REVISION_CONFLICT", "message": "Scene revision conflict.", "details": { "expected_revision": 1, "current_revision": 2 } }
```

## 7. 本地启动

```powershell
cd backend
python -m pip install -r requirements.txt
Copy-Item .env.example .env
supabase start
docker compose up -d redis
python -m app.db.init_db
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

如果本机已有旧 `supabase_db_backend` 卷，可能会出现 Postgres 15 数据目录无法由 Postgres 17 镜像启动的问题。本实现已将 `project_id` 改为 `vc_simulation_backend`，避免删除旧卷并创建独立的新本地 Supabase 数据卷。

## 8. 校验结果

本轮已完成以下校验：

- JSON 语法校验：`docs/business/SimulationSchema` 与 `backend` 下 38 个 JSON 文件全部可解析。
- Schema 契约一致性：8 个默认 DeviceSpec、`2.SceneDocument/example.json`、`demo/pallet_sorting_line/full_chain_schema.json` 的端口、接口、绑定、边端点和 TopologyGraph 映射通过自定义一致性校验，0 error、0 warning。
- Python 编译：`python -m compileall backend/app` 通过。
- 单元测试：`cd backend; python -m pytest -q` 通过，结果 `11 passed`。
- 已新增 `backend/app/services/signal_bus_runtime.py` 与 `backend/tests/test_signal_bus_runtime.py`，覆盖无消费者、单消费者、fan-out、disabled edge、identity transform、DB 事件落库。
- 已新增 `backend/tests/test_schema_contracts.py`，将 DeviceSpec 分层接口、SceneDocument 三类 edge、demo TopologyGraph 映射纳入自动化回归。
- Redis：`vc-simulation-redis` 通过 `PONG`，并验证 snapshot 写/读、signal set/get、runtime clear。
- Supabase：`supabase start` 成功，migration 与 seed 已执行；`projects`、`assets`、`device_specs`、`scenes`、`scene_events`、`scene_topologies`、`simulation_runs`、`simulation_events` 均存在。
- HTTP 服务：临时启动 `uvicorn app.main:app --host 127.0.0.1 --port 8000`，`GET /health` 返回 `{"status":"ok","service":"VC Simulation Backend","agent_enabled":false}`。
- 真实 DB + Redis 业务链路：导入 8 个默认设备、创建项目和场景实例、创建 process edge、编译出 1 条 physical edge 和 6 条 signal edge、重建 topology、创建 simulation run、emit signal、写 runtime snapshot、清理 runtime state，全部通过。

## 9. 已知边界

- `docs/business/SimulationSchema/*.schema.json` 当前是“规范契约 JSON”，不是严格 JSON Schema Draft，因此需要继续保留业务级自定义校验。
- 当前 backend 没有 Agent 表、Agent 路由、LLM provider 配置，也没有自动生成 SceneBehaviorGraph 的能力。
- `InterfaceCompiler` 当前用确定性规则和信号名启发式生成 signal edge，后续可替换为更强的设备行为编译器。
- 物理连接只做端点和 material class 基础校验，尚未实现基于真实 transform/local_frame 的距离、朝向、snap tolerance 计算。
