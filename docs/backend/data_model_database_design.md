# 数据结构与数据库方案

> 版本：v0.1  
> 日期：2026-08-19  
> 目标：定义场景事实、三层接口、信号运行时模型，以及 Supabase/Postgres/Redis/Storage 的职责。

---

## 1. 存储分工

| 存储 | 解决的业务问题 | 不负责 |
|---|---|---|
| Supabase Postgres | 场景事实、设备规范、Agent run、SimPlan、审计事件、可恢复历史。 | 高频仿真帧。 |
| Supabase Storage | GLB、缩略图、上传文档、导出文件。 | 结构化查询。 |
| Redis | runtime state、任务队列、锁、stream、仿真帧、临时缓存。 | 长期事实数据。 |

Redis 不是事实库。Redis 清空后，系统必须能从 Postgres 的 scene、SimPlan、simulation run 和 event log 恢复到可诊断状态。

---

## 2. DeviceSpec

`DeviceSpec` 是前端属性面板、接口编译、拓扑构建、Agent 校验和仿真 runtime 的共同约束来源。

```json
{
  "spec_id": "spec_robot_arm_v1",
  "device_type": "robot",
  "version": "1.0.0",
  "display_name": "Robot Arm",
  "asset_defaults": {
    "model_format": "glb",
    "model_key": "models/robot/robot_arm.glb"
  },
  "param_schema": {
    "speed_mps": { "type": "number", "min": 0.05, "max": 2.0, "default": 0.5 }
  },
  "physical_interfaces": [
    {
      "interface_id": "pick_area",
      "kind": "material",
      "direction": "input",
      "node_name": "PickAnchor",
      "local_position": [0.0, 0.0, 0.0],
      "local_forward": [1.0, 0.0, 0.0],
      "material_classes": ["box"]
    },
    {
      "interface_id": "place_area",
      "kind": "material",
      "direction": "output",
      "node_name": "PlaceAnchor",
      "local_position": [0.0, 0.0, 0.0],
      "local_forward": [1.0, 0.0, 0.0],
      "material_classes": ["box"]
    }
  ],
  "process_ports": [
    { "port_id": "flow_input", "direction": "input", "label": "Input" },
    { "port_id": "flow_output", "direction": "output", "label": "Output" }
  ],
  "signal_ports": [
    { "port_id": "start_pick", "direction": "input", "payload_schema": { "material_id": "string" } },
    { "port_id": "busy", "direction": "output", "payload_schema": { "value": "boolean" } },
    { "port_id": "done", "direction": "output", "payload_schema": { "material_id": "string" } }
  ],
  "interface_bindings": [
    { "process_port": "flow_input", "physical_interface": "pick_area" },
    { "process_port": "flow_output", "physical_interface": "place_area" },
    { "signal_port": "done", "emitted_by": "action.pick_and_place.completed" }
  ],
  "actions": [
    {
      "action_type": "pick_and_place",
      "default_algorithm": "robot_pick_place",
      "required_physical_interfaces": ["pick_area", "place_area"],
      "input_signals": ["start_pick"],
      "output_signals": ["busy", "done"]
    }
  ],
  "runtime_contract": {
    "fsm_states": ["idle", "busy", "error"],
    "default_state": "idle",
    "resources": ["robot_arm", "gripper"]
  }
}
```

---

## 3. SceneDocument

```json
{
  "scene_id": "scene_01",
  "project_id": "project_01",
  "schema_version": "scene/v1",
  "revision": 42,
  "unit": "m",
  "coordinate_system": "threejs-y-up",
  "instances": [],
  "process_edges": [],
  "physical_edges": [],
  "signal_edges": [],
  "runtime_config": {
    "default_sim_duration_s": 1800,
    "signal_timeout_s": 30,
    "deadlock_detection": true
  }
}
```

### 3.1 DeviceInstance

```json
{
  "instance_id": "conveyor_1",
  "spec_id": "spec_conveyor_v1",
  "device_type": "conveyor",
  "name": "Conveyor 1",
  "transform": {
    "position": [0.0, 0.0, 0.0],
    "rotation_euler": [0.0, 0.0, 0.0],
    "scale": [1.0, 1.0, 1.0]
  },
  "params": {
    "speed_mps": 0.3
  },
  "visible": true,
  "locked": false
}
```

### 3.2 ProcessEdge

```json
{
  "edge_id": "proc_edge_001",
  "source_instance_id": "conveyor_1",
  "source_interface": "flow_output",
  "target_instance_id": "robot_1",
  "target_interface": "flow_input",
  "edge_type": "material_flow",
  "status": "confirmed"
}
```

### 3.3 PhysicalEdge

```json
{
  "edge_id": "phy_edge_001",
  "from_port": "conveyor_1.exit",
  "to_port": "robot_1.pick_area",
  "edge_type": "material_transfer",
  "status": "compiled",
  "source_process_edge_id": "proc_edge_001"
}
```

### 3.4 SignalEdge

```json
{
  "edge_id": "sig_edge_001",
  "source_instance_id": "conveyor_1",
  "source_signal": "part_ready",
  "target_instance_id": "robot_1",
  "target_signal": "start_pick",
  "edge_type": "control_signal",
  "default_timeout_s": 10.0,
  "status": "planned"
}
```

---

## 4. SignalRuntimeModel

信号实时通信分四层。

### 4.1 静态层

保存在 Postgres 的 `DeviceSpec.signal_ports` 和 `SceneDocument.signal_edges`。

职责：定义设备能发什么、收什么、payload schema、默认 timeout、静态 wiring。

### 4.2 计划层

保存在 Postgres 的 `sim_plans.document`。

```json
{
  "signal_bindings": [
    {
      "when": "conveyor_1.part_ready",
      "trigger": "robot_1.start_pick",
      "timeout_s": 10,
      "on_timeout": "emit_observation"
    },
    {
      "when": "robot_1.busy",
      "effect": "conveyor_1.exit.waiting_downstream"
    },
    {
      "when": "robot_1.done",
      "effect": "conveyor_1.release_waiting_material"
    }
  ]
}
```

职责：表达本次仿真中信号如何驱动动作、等待、超时和失败策略。

### 4.3 运行层

存在 Simulation Runtime 内存和 Redis。

```json
{
  "simulation_run_id": "sim_run_01",
  "signals": {
    "robot_1.busy": { "value": true, "updated_at_sim_time_s": 12.0 },
    "robot_1.done": { "value": false, "updated_at_sim_time_s": 12.0 }
  },
  "device_states": {
    "robot_1": "busy",
    "conveyor_1": "waiting_downstream"
  },
  "wait_queues": {
    "conveyor_1.exit": ["box_001"]
  },
  "resource_locks": {
    "robot_1.gripper": "box_000"
  }
}
```

职责：实时决定设备 FSM 状态、等待队列、资源锁和信号值。

### 4.4 事件层

Redis Streams + WebSocket 推送实时事件；关键摘要写入 Postgres 审计表。

事件示例：

```json
{
  "type": "signal_event",
  "simulation_run_id": "sim_run_01",
  "sim_time_s": 16.8,
  "source": "robot_1.done",
  "target": "conveyor_1.release_waiting_material",
  "payload": { "material_id": "box_001" }
}
```

---

## 5. Postgres 表

核心表：

```sql
projects
project_members
assets
device_specs
scenes
scene_events
scene_topologies
agent_threads
agent_runs
agent_events
agent_artifacts
sim_plans
simulation_runs
simulation_events
```

### 5.1 scenes

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
```

### 5.2 device_specs

```sql
CREATE TABLE device_specs (
  id UUID PRIMARY KEY,
  spec_key TEXT UNIQUE NOT NULL,
  device_type TEXT NOT NULL,
  version TEXT NOT NULL,
  document JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 5.3 simulation_runs

```sql
CREATE TABLE simulation_runs (
  id UUID PRIMARY KEY,
  project_id UUID NOT NULL REFERENCES projects(id),
  scene_id UUID NOT NULL REFERENCES scenes(id),
  sim_plan_id UUID NOT NULL REFERENCES sim_plans(id),
  base_scene_revision BIGINT NOT NULL,
  status TEXT NOT NULL,
  runtime_snapshot JSONB,
  metrics_summary JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 5.4 simulation_events

```sql
CREATE TABLE simulation_events (
  id UUID PRIMARY KEY,
  simulation_run_id UUID NOT NULL REFERENCES simulation_runs(id),
  sim_time_s DOUBLE PRECISION,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

`simulation_events` 保存低频关键摘要和 observation；高频帧只进 Redis/WebSocket。

---

## 6. Redis 设计

### 6.1 Keys

```text
runtime:simulation:{run_id}:state          HASH
runtime:simulation:{run_id}:signals        HASH
runtime:simulation:{run_id}:device_states  HASH
runtime:simulation:{run_id}:wait_queues    HASH or LIST per queue
runtime:simulation:{run_id}:locks          HASH
agent:run:{run_id}:status                  HASH
lock:scene:{scene_id}                      STRING with TTL
```

### 6.2 Streams

```text
stream:project:{project_id}:events
stream:simulation:{run_id}:events
stream:simulation:{run_id}:frames
stream:agent:{run_id}:events
```

Redis Streams 用于：

- Realtime Hub 订阅并推 WebSocket。
- 指标聚合器消费仿真事件。
- 审计写入器把关键事件落 Postgres。
- 断线客户端补读最近事件。

---

## 7. Supabase Storage

Buckets：

```text
models/          GLB 文件
thumbnails/      设备和项目缩略图
uploads/         用户上传文档
exports/         导出 scene / sim report
```

当前只支持 GLB：

```json
{
  "asset_id": "asset_robot_01",
  "bucket": "models",
  "path": "robot/robot_arm.glb",
  "mime_type": "model/gltf-binary"
}
```

后续如切 S3/MinIO，保持数据库字段为 `bucket/path/provider`，业务代码通过 Storage adapter 访问。

---

## 8. 恢复能力

Redis 清空后，系统恢复路径：

1. 从 `scenes.current_document` 读取场景事实。
2. 从 `device_specs.document` 读取接口和运行契约。
3. 从 `sim_plans.document` 读取计划。
4. 从 `simulation_runs.runtime_snapshot` 或 `simulation_events` 恢复可诊断状态。
5. 重新建立 Redis runtime keys 和 streams。

如果没有 runtime snapshot，只能恢复到“可诊断/可重跑”状态，不承诺从精确仿真时刻继续执行。

---

## 9. 验收标准

- `SceneDocument` 不再出现混合语义的单一 `edges`。
- `DeviceSpec` 覆盖三层接口和 `runtime_contract`。
- Signal runtime 当前值、等待队列和 FSM 状态不写入 scene document。
- Redis 状态可重建，不影响 Postgres 中的场景事实和审计。
- GLB 文件能通过 Supabase Storage bucket/path 被前端加载。

