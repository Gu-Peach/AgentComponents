# 后端接口设计

> 版本：v0.1  
> 日期：2026-08-19  
> 目标：定义场景、接口、拓扑、Agent、仿真和实时事件的后端 API 边界。

---

## 1. API 分工

| 通道 | 用途 | 不负责 |
|---|---|---|
| REST | 创建资源、读取快照、提交命令、打断/恢复 run。 | 高频仿真帧推送。 |
| SSE | Agent run 节点流、LLM token、artifact、等待用户、完成事件。 | 前端到后端控制命令。 |
| WebSocket | 场景协同、信号事件、设备状态、仿真帧、终端日志。 | Agent 文本生成流。 |

所有会修改场景事实的接口都必须携带 `base_revision`。后端写入前检查当前 scene revision，冲突时返回 `SCENE_REVISION_CONFLICT`，由前端或 Agent 重新加载后 rebase。

---

## 2. 通用约定

### 2.1 路径前缀

```http
/api/projects/{project_id}/...
/api/agent/...
/api/simulation-runs/...
/ws/projects/{project_id}/events
```

### 2.2 写入请求约定

```json
{
  "base_revision": 42,
  "payload": {}
}
```

### 2.3 写入响应约定

```json
{
  "scene_id": "scene_01",
  "previous_revision": 42,
  "new_revision": 43,
  "event_id": "evt_01",
  "document": {}
}
```

### 2.4 错误响应约定

```json
{
  "error": "SCENE_REVISION_CONFLICT",
  "message": "Scene changed after this request was prepared.",
  "details": {
    "expected_revision": 42,
    "current_revision": 45
  }
}
```

---

## 3. 设备实例接口

场景由设备实例组合而成，因此实例接口是最核心的场景写入接口。

```http
GET    /api/projects/{project_id}/scene/instances
POST   /api/projects/{project_id}/scene/instances
GET    /api/projects/{project_id}/scene/instances/{instance_id}
PATCH  /api/projects/{project_id}/scene/instances/{instance_id}
DELETE /api/projects/{project_id}/scene/instances/{instance_id}
```

### 3.1 添加实例

```json
{
  "base_revision": 42,
  "spec_id": "spec_conveyor_belt_v1",
  "instance_id": "conveyor_3",
  "name": "Conveyor 3",
  "transform": {
    "position": [3.2, 0.0, 1.0],
    "rotation_euler": [0.0, 1.5708, 0.0],
    "scale": [1.0, 1.0, 1.0]
  },
  "params_override": {
    "speed_mps": 0.4
  }
}
```

后端职责：

- 校验 `spec_id` 存在。
- 生成或校验 `instance_id` 场景内唯一。
- 用 `DeviceSpec.param_schema` 合并默认参数和覆盖参数。
- 写入 `scene_events`，scene revision +1。
- 发布 `scene_event.device_added`。

### 3.2 更新实例

支持局部修改：

- `name`
- `transform`
- `params`
- `visible`
- `locked`
- `semantic_tags`

更新 transform 或参数后，后端应标记当前拓扑缓存失效，因为真实接口世界坐标可能改变。

### 3.3 删除实例

```json
{
  "base_revision": 42,
  "delete_policy": "stage_for_confirmation"
}
```

`delete_policy`：

| 策略 | 行为 |
|---|---|
| `reject_if_connected` | 如果实例仍有关联流程/物理/信号连接，拒绝删除。 |
| `delete_incident_edges` | 删除实例并删除所有关联边。 |
| `stage_for_confirmation` | 返回删除预案和受影响连接，等待用户确认。 |

---

## 4. 三类连接接口

### 4.1 流程连接 process-edges

流程连接对齐前端 Interface 画布，只保存用户可理解的工艺流。

```http
GET    /api/projects/{project_id}/scene/process-edges
POST   /api/projects/{project_id}/scene/process-edges
PATCH  /api/projects/{project_id}/scene/process-edges/{edge_id}
DELETE /api/projects/{project_id}/scene/process-edges/{edge_id}
```

创建示例：

```json
{
  "base_revision": 42,
  "source_instance_id": "conveyor_1",
  "source_interface": "flow_output",
  "target_instance_id": "robot_1",
  "target_interface": "flow_input",
  "edge_type": "material_flow"
}
```

后端校验：

- source / target instance 必须存在。
- source / target interface 必须存在于各自 `process_ports`。
- 第一阶段只允许 `flow_output -> flow_input`。
- 禁止连接 locked 实例，除非请求带有明确 override 权限。
- 写入后标记接口编译结果和拓扑缓存失效。

### 4.2 物理连接 physical-edges

物理连接是执行层真实接口连接，可以来自接口编译、显式对齐、后续隐式拓扑确认。

```http
GET    /api/projects/{project_id}/scene/physical-edges
POST   /api/projects/{project_id}/scene/physical-edges
DELETE /api/projects/{project_id}/scene/physical-edges/{edge_id}
```

请求示例：

```json
{
  "base_revision": 42,
  "from_port": "conveyor_1.exit",
  "to_port": "robot_1.pick_area",
  "edge_type": "material_transfer",
  "source_process_edge_id": "proc_edge_001"
}
```

后端校验：

- `from_port` / `to_port` 必须能解析为真实物理接口。
- material class 必须兼容。
- 方向必须兼容：output -> input 或 output -> input_output。
- 如果来自 process edge，应保存 `source_process_edge_id` 便于审计。

### 4.3 信号连接 signal-edges

信号连接表达设备间的事件或控制信号依赖。第一阶段可以不开放完整 UI 编辑，但 API 需要存在，供 Agent 和仿真计划使用。

```http
GET    /api/projects/{project_id}/scene/signal-edges
POST   /api/projects/{project_id}/scene/signal-edges
DELETE /api/projects/{project_id}/scene/signal-edges/{edge_id}
```

请求示例：

```json
{
  "base_revision": 42,
  "source_instance_id": "conveyor_1",
  "source_signal": "part_ready",
  "target_instance_id": "robot_1",
  "target_signal": "start_pick",
  "edge_type": "control_signal",
  "default_timeout_s": 10.0
}
```

后端校验：

- source signal 必须是 output signal。
- target signal 必须是 input signal。
- signal payload schema 必须兼容。
- signal edge 不代表实时状态，只代表静态 wiring / rule。

---

## 5. 接口编译接口

接口编译把前端流程口连接转换为执行层真实接口和信号依赖。

```http
POST /api/projects/{project_id}/interfaces/compile
```

请求：

```json
{
  "base_revision": 42,
  "mode": "dry_run"
}
```

`mode`：

| 模式 | 行为 |
|---|---|
| `dry_run` | 只返回编译结果和 warnings，不写入 scene。 |
| `apply` | 将编译出的 `physical_edges` / `signal_edges` 写回 scene，revision +1。 |

响应：

```json
{
  "scene_revision": 42,
  "compiled_physical_edges": [
    {
      "from_port": "conveyor_1.exit",
      "to_port": "robot_1.pick_area",
      "source_process_edge_id": "proc_edge_001"
    }
  ],
  "compiled_signal_edges": [
    {
      "source_signal": "conveyor_1.part_ready",
      "target_signal": "robot_1.start_pick"
    }
  ],
  "warnings": []
}
```

如果缺少 binding：

```json
{
  "warnings": [
    {
      "code": "MISSING_BINDING",
      "process_edge_id": "proc_edge_001",
      "message": "robot_1.flow_input has no physical interface binding."
    }
  ],
  "compiled_physical_edges": []
}
```

---

## 6. 拓扑接口

```http
POST /api/projects/{project_id}/topology/rebuild
GET  /api/projects/{project_id}/topology?scene_revision=latest
POST /api/projects/{project_id}/topology/candidate-edges/{candidate_id}/confirm
POST /api/projects/{project_id}/topology/candidate-edges/{candidate_id}/reject
GET  /api/projects/{project_id}/topology/reachability?from=conveyor_1.exit&to=storage_1.A2
```

拓扑 rebuild 输入来自：

- `instances`
- `DeviceSpec.physical_interfaces`
- `process_edges`
- `physical_edges`
- `signal_edges`
- 用户确认/拒绝过的候选边历史

第一阶段拓扑以显式流程连接和接口编译为主；隐式拓扑候选作为 Phase 2.5 算法模块输出，不自动写入 scene。

---

## 7. Agent 接口

```http
POST /api/projects/{project_id}/agent/threads
GET  /api/projects/{project_id}/agent/threads

POST /api/agent/threads/{thread_id}/runs
GET  /api/agent/runs/{run_id}
GET  /api/agent/runs/{run_id}/events
GET  /api/agent/runs/{run_id}/stream

POST /api/agent/runs/{run_id}/interrupt
POST /api/agent/runs/{run_id}/resume
POST /api/agent/runs/{run_id}/cancel
POST /api/agent/runs/{run_id}/apply-artifact
```

创建 run：

```json
{
  "message": "让机器人把传送带出口的物料搬到右侧传送带，然后运行仿真",
  "scene_revision": 42,
  "mode": "plan_and_apply",
  "approval_policy": "require_before_scene_write",
  "attachments": []
}
```

Agent SSE 事件：

```json
{ "type": "node_started", "node": "compile_interfaces" }
{ "type": "artifact_created", "artifact_type": "sim_plan", "artifact_id": "art_01" }
{ "type": "interrupt_required", "reason": "ambiguous_target", "questions": [] }
{ "type": "done", "result": {} }
```

运行中打断：

```json
{
  "kind": "revise",
  "message": "停一下，不要用 robot_1，用 robot_2",
  "strategy": "pause_at_safe_point"
}
```

---

## 8. 仿真与实时接口

### 8.1 仿真控制

```http
POST /api/projects/{project_id}/sim-plans
GET  /api/projects/{project_id}/sim-plans/{plan_id}

POST /api/projects/{project_id}/simulation-runs
GET  /api/projects/{project_id}/simulation-runs/{run_id}
POST /api/simulation-runs/{run_id}/pause
POST /api/simulation-runs/{run_id}/resume
POST /api/simulation-runs/{run_id}/stop
GET  /api/simulation-runs/{run_id}/events
GET  /api/simulation-runs/{run_id}/metrics
```

### 8.2 WebSocket 实时事件

```http
WS /ws/projects/{project_id}/events
```

事件类型：

| 事件 | 用途 |
|---|---|
| `signal_event` | 信号值变化、发送、接收、超时。 |
| `device_state_changed` | 设备 FSM 状态变化，例如 `idle -> busy`。 |
| `material_waiting` | 物料因下游设备 busy 或资源不可用进入等待。 |
| `action_started` | 仿真动作开始。 |
| `action_completed` | 仿真动作完成。 |
| `simulation_frame` | 前端动画帧数据。 |
| `simulation_observation` | 死锁、超时、目标未达成等可触发 Agent 的观察事件。 |

示例：

```json
{
  "type": "material_waiting",
  "simulation_run_id": "sim_run_01",
  "sim_time_s": 12.4,
  "material_id": "box_001",
  "at": "conveyor_1.exit",
  "waiting_for": "robot_1.busy=false"
}
```

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

## 9. 验收场景

- 添加/删除 conveyor、robot、workpiece 后 revision 正确递增。
- 删除 connected device 时三种 delete policy 行为正确。
- `flow_output -> flow_input` 能 dry-run 编译成真实接口；缺少 binding 时只返回 warning。
- robot busy 时 conveyor 输出物料进入等待，robot done 后等待物料继续流转。
- 用户运行中 interrupt 后 simulation 暂停，Agent 基于 snapshot 生成修订 artifact。

