# conveyor template 字段说明

本文用于解释 `conveyor/template.json` 中每个板块和字段的含义，作为后续编写传送带类 `DeviceSpec` 的填写说明。

## 当前结论：传送带需要停留点模型

所有传送带都应支持“停留点 / 占位点”建模。停留点不是新的设备，而是传送带本体能力的一部分：`DeviceSpec` 定义停留点如何由 `entry` 和 `exit` 坐标生成，`SceneDocument` 通过实例参数决定本场景使用几个停留点，`SceneBehaviorGraph` 定义停留点如何参与队列、阻塞、释放和行为触发，`RuntimeSnapshot` 保存当前每个停留点的占用状态。

第一阶段采用线性插值：

```text
point(t) = entry + t * (exit - entry)
```

其中 `t` 从 `0` 到 `1`，`0` 表示入口停留点，`1` 表示出口停留点。后续如果需要弯曲传送带，可以扩展为 `polyline_interpolation`。

## 1. 模板定位

`conveyor/template.json` 是传送带设备本体的填写模板，不是某一个场景中的设备实例。它描述一类传送带设备应具备的本体信息，包括资产、参数、接口、信号、行为、运行契约和传送带专属运动规则。

场景级 schema 会通过 `SceneDocument.instances[].spec_id` 引用具体传送带 `DeviceSpec`，并在场景中赋予实例 ID、位姿、参数覆盖和连接关系。

## 2. 占位符规则

模板中的字符串后缀用于说明字段填写要求。

| 后缀        | 含义                                           |
| ----------- | ---------------------------------------------- |
| `_required` | 必填字段，创建具体设备规范时必须替换为真实值。 |
| `_optional` | 可选字段，可填写真实值，也可由系统推断或留空。 |
| `{file}`    | 文件名占位符，需要替换为具体模型文件名。       |

## 3. 通用元信息

```json
{
  "schema_id": "conveyor_template_required",
  "schema_type": "DeviceSpecTemplate",
  "version": "0.1.0",
  "name": "传送带设备本体填写模板",
  "description": "用于新增传送带 DeviceSpec。",
  "source": {},
  "created_for": "conveyor 设备本体建模",
  "references": [],
  "notes": []
}
```

| 字段          | 含义                                                                  |
| ------------- | --------------------------------------------------------------------- |
| `schema_id`   | 当前模板文件的唯一标识。                                              |
| `schema_type` | 当前 JSON 的类型；这里是 `DeviceSpecTemplate`，表示设备规范填写模板。 |
| `version`     | 模板版本，用于后续 schema 演进和兼容性判断。                          |
| `name`        | 模板展示名称。                                                        |
| `description` | 模板用途说明。                                                        |
| `source.kind` | 模板来源类型；`manual_template` 表示人工设计的填写模板。              |
| `source.path` | 当前模板文件路径，便于追踪来源。                                      |
| `created_for` | 模板服务的建模对象或业务目的。                                        |
| `references`  | 当前模板依赖或参考的规范、示例文件。                                  |
| `notes`       | 额外说明；传送带模板中强调 `entry` / `exit` 是最小必填物理接口。      |

## 4. 设备标识

```json
{
  "device_spec_id": "conveyor_id_required",
  "device_type": "conveyor",
  "display_name": "传送带展示名_required"
}
```

| 字段             | 含义                                                |
| ---------------- | --------------------------------------------------- |
| `device_spec_id` | 设备本体规范 ID。具体场景通过这个 ID 引用设备规范。 |
| `device_type`    | 设备类型；传送带固定为 `conveyor`。                 |
| `display_name`   | 面向界面、文档和调试日志展示的设备名称。            |

## 5. 资产信息 `asset`

```json
"asset": {
  "model_format": "glb_required",
  "model_key": "assets/models/conveyor/{file}.glb_required"
}
```

| 字段           | 含义                                               |
| -------------- | -------------------------------------------------- |
| `model_format` | 三维模型格式；当前阶段默认使用 `glb`。             |
| `model_key`    | 模型资产路径或对象存储 key，用于前端加载三维模型。 |

`asset` 只描述模型资源位置，不描述设备运行逻辑。设备运行逻辑由接口、行为、信号和运行契约描述。

## 6. 参数定义 `params_schema`

```json
"params_schema": {
  "speed_mps": {
    "type": "number",
    "default": "速度_required",
    "unit": "m/s"
  },
  "capacity": {
    "type": "integer",
    "default": "容量_required"
  },
  "resume_threshold": {
    "type": "integer",
    "default": "恢复阈值_required"
  },
  "stop_point_count": {
    "type": "integer",
    "default": "停留点数量_required"
  }
}
```

| 字段                | 含义                                                               |
| ------------------- | ------------------------------------------------------------------ |
| `params_schema`     | 传送带可配置参数集合。场景实例可以基于这些参数做覆盖。             |
| `speed_mps`         | 传送带运行速度，单位为米/秒，用于计算物料从入口到出口的输送时间。  |
| `speed_mps.type`    | 参数类型；`number` 表示数值型参数。                                |
| `speed_mps.default` | 默认速度，创建具体设备规范时必须给出。                             |
| `speed_mps.unit`    | 参数单位；`m/s` 表示米/秒。                                        |
| `capacity`          | 传送带最大承载数量，用于判断是否可接收新物料、是否进入等待或阻塞。 |
| `capacity.type`     | 参数类型；`integer` 表示整数。                                     |
| `capacity.default`  | 默认容量，创建具体设备规范时必须给出。                             |
| `resume_threshold` | blocked 后恢复接收的负载阈值。 |
| `stop_point_count` | 默认停留点数量；场景实例可通过 `param_overrides.stop_point_count` 覆盖。 |

## 7. 物理接口 `physical_interfaces`

```json
"physical_interfaces": [
  {
    "interface_id": "entry",
    "kind": "material",
    "direction": "input",
    "node_name": "EntryAnchor_required",
    "material_classes": ["workpiece_required"],
    "local_position": ["x_optional", "y_optional", "z_optional"],
    "local_forward": ["x_optional", "y_optional", "z_optional"]
  },
  {
    "interface_id": "exit",
    "kind": "material",
    "direction": "output",
    "node_name": "ExitAnchor_required",
    "material_classes": ["workpiece_required"],
    "local_position": ["x_optional", "y_optional", "z_optional"],
    "local_forward": ["x_optional", "y_optional", "z_optional"]
  }
]
```

`physical_interfaces` 描述物料在三维设备上真实进入和离开的位置，是场景物理连接、运行时物料转移和前端动画定位的重要依据。

| 字段               | 含义                                                                    |
| ------------------ | ----------------------------------------------------------------------- |
| `interface_id`     | 物理接口 ID。传送带最小接口为 `entry` 和 `exit`。                       |
| `kind`             | 接口类型；`material` 表示该接口用于物料流转。                           |
| `direction`        | 接口方向；`input` 表示入料，`output` 表示出料。                         |
| `node_name`        | 三维模型中的锚点节点名，用于把接口绑定到 GLB 模型节点。                 |
| `material_classes` | 支持通过该接口流转的物料类型，例如 `workpiece` 或 `workpiece_carrier`。 |
| `local_position`   | 接口在设备局部坐标系下的位置，可用于没有模型锚点或需要修正定位的情况。  |
| `local_forward`    | 接口在设备局部坐标系下的朝向向量，用于判断对接方向和物料运动方向。      |

### `entry`

`entry` 是传送带入料接口。上游设备释放物料后，运行时会把物料转移到该接口附近，再触发传送带的接收或输送行为。

### `exit`

`exit` 是传送带出料接口。物料到达该接口后，传送带可以向下游发送 `part_ready`，并等待下游接收或释放。

## 8. 工艺流程口 `process_ports`

```json
"process_ports": [
  {
    "port_id": "flow_input",
    "direction": "input",
    "label": "Input"
  },
  {
    "port_id": "flow_output",
    "direction": "output",
    "label": "Output"
  }
]
```

`process_ports` 是工艺层抽象接口，用于描述设备在工艺流程中的输入和输出关系。它不直接表示三维模型上的位置，而是给场景流程编排和 Agent 规划使用。

| 字段        | 含义                                                      |
| ----------- | --------------------------------------------------------- |
| `port_id`   | 工艺流程口 ID。                                           |
| `direction` | 流程口方向；`input` 表示工艺流入，`output` 表示工艺流出。 |
| `label`     | 流程画布或配置界面展示名称。                              |

| 流程口        | 含义                           |
| ------------- | ------------------------------ |
| `flow_input`  | 传送带在工艺流程中的抽象入口。 |
| `flow_output` | 传送带在工艺流程中的抽象出口。 |

## 9. 信号端口 `signal_ports`

```json
"signal_ports": [
  {
    "port_id": "part_ready",
    "direction": "output",
    "value_type": "event"
  },
  {
    "port_id": "blocked",
    "direction": "output",
    "value_type": "boolean"
  },
  {
    "port_id": "capacity_available",
    "direction": "output",
    "value_type": "event"
  },
  {
    "port_id": "stop_point_occupied",
    "direction": "output",
    "value_type": "event"
  },
  {
    "port_id": "stop_point_released",
    "direction": "output",
    "value_type": "event"
  },
  {
    "port_id": "done",
    "direction": "output",
    "value_type": "event"
  },
  {
    "port_id": "release_waiting_material",
    "direction": "input",
    "value_type": "event"
  }
]
```

`signal_ports` 描述设备运行时可以收发的事件和值。信号用于设备之间的实时协同，例如到料通知、阻塞传播和等待释放。

| 字段         | 含义                                                            |
| ------------ | --------------------------------------------------------------- |
| `port_id`    | 信号端口 ID。                                                   |
| `direction`  | 信号方向；`input` 表示设备接收信号，`output` 表示设备发出信号。 |
| `value_type` | 信号值类型；`event` 表示瞬时事件，`boolean` 表示布尔状态。      |

| 信号                       | 方向     | 类型      | 含义                                                           |
| -------------------------- | -------- | --------- | -------------------------------------------------------------- |
| `part_ready`               | `output` | `event`   | 物料到达 `exit` 后发出的到料事件，用于通知下游设备接收或抓取。 |
| `blocked`                  | `output` | `boolean` | 传送带进入阻塞状态时输出的状态信号。                           |
| `capacity_available`       | `output` | `event`   | 停留点释放且负载低于恢复阈值后发出的恢复接收事件。             |
| `stop_point_occupied`      | `output` | `event`   | 某个停留点被物料或载具占用时发出的事件。                       |
| `stop_point_released`      | `output` | `event`   | 某个停留点被释放时发出的事件。                                 |
| `done`                     | `output` | `event`   | 单次输送行为完成时发出的事件。                                 |
| `release_waiting_material` | `input`  | `event`   | 下游设备释放等待条件时输入的事件，用于推进或释放等待物料。     |

## 10. 接口绑定 `interface_bindings`

```json
"interface_bindings": [
  {
    "process_port": "flow_input",
    "physical_interface": "entry"
  },
  {
    "process_port": "flow_output",
    "physical_interface": "exit"
  }
]
```

`interface_bindings` 描述工艺流程口和真实物理接口之间的映射关系。工艺层使用 `flow_input` / `flow_output` 编排流程，运行时通过绑定关系找到真实的 `entry` / `exit`。

| 字段                 | 含义                          |
| -------------------- | ----------------------------- |
| `process_port`       | 工艺流程口 ID。               |
| `physical_interface` | 与该流程口对应的物理接口 ID。 |

| 绑定关系              | 含义                                               |
| --------------------- | -------------------------------------------------- |
| `flow_input -> entry` | 工艺流入传送带时，物料实际进入 `entry` 物理接口。  |
| `flow_output -> exit` | 工艺流出传送带时，物料实际从 `exit` 物理接口离开。 |

## 11. 输送行为 `transport_behaviors`

```json
"transport_behaviors": [
  {
    "behavior_id": "accept_material",
    "behavior_type": "material_transfer",
    "input_physical_interface": "entry",
    "output_signals": ["stop_point_occupied"]
  },
  {
    "behavior_id": "advance_to_next_stop_point",
    "behavior_type": "stop_point_buffered_transport",
    "input_physical_interface": "entry",
    "output_physical_interface": "exit",
    "default_algorithm": "linear_stop_point_motion",
    "output_signals": ["stop_point_occupied", "stop_point_released"]
  },
  {
    "behavior_id": "transport_to_exit",
    "behavior_type": "stop_point_buffered_transport",
    "input_physical_interface": "entry",
    "output_physical_interface": "exit",
    "default_algorithm": "linear_stop_point_motion",
    "output_signals": ["part_ready", "done", "stop_point_released"]
  },
  {
    "behavior_id": "release_material",
    "behavior_type": "handoff",
    "input_signals": ["release_waiting_material"],
    "output_physical_interface": "exit"
  }
]
```

`transport_behaviors` 描述传送带设备本体具备的行为能力。它定义设备能执行哪些物料流转动作，以及这些动作依赖哪些接口、信号和算法。

| 字段                        | 含义                                                        |
| --------------------------- | ----------------------------------------------------------- |
| `behavior_id`               | 行为 ID，用于 SceneBehaviorGraph 和 Runtime 引用。 |
| `behavior_type`             | 行为类型，用于运行时选择执行逻辑。                          |
| `input_physical_interface`  | 行为读取物料的输入物理接口。                                |
| `output_physical_interface` | 行为输出物料的物理接口。                                    |
| `default_algorithm`         | 默认执行算法名称。传送带停留点输送使用 `linear_stop_point_motion`。 |
| `input_signals`             | 触发该行为所需的输入信号。                                  |
| `output_signals`            | 行为完成或到达关键状态时输出的信号。                        |

| 行为                | 含义                                                                    |
| ------------------- | ----------------------------------------------------------------------- |
| `accept_material`   | 从 `entry` 接收物料，将物料纳入传送带当前承载集合。                     |
| `advance_to_next_stop_point` | 将物料从当前停留点推进到下一个可用停留点。 |
| `transport_to_exit` | 按停留点感知输送模型将物料推进到出口停留点，到达后输出 `part_ready` 和 `done`。 |
| `release_material`  | 在收到 `release_waiting_material` 后，从 `exit` 向下游释放物料。        |

## 12. 运行契约 `runtime_contract`

```json
"runtime_contract": {
  "fsm_states": ["idle", "moving", "waiting_downstream", "blocked", "error"],
  "default_state": "idle",
  "resources": [
    {
      "resource_id": "belt_surface",
      "exclusive": false
    }
  ],
    "capacity": {
      "max_active_materials": "容量_required",
      "queue_id": "stop_point_queue",
      "resume_threshold": "恢复阈值_required"
  },
  "error_policy": {
    "on_downstream_timeout": "emit_observation"
  }
}
```

`runtime_contract` 描述传送带在仿真运行时需要遵守的状态、资源、容量和异常处理规则。它主要服务 Runtime、Scheduler、DeviceFSM 和 Runtime 临时调度视图。

### 12.1 状态机字段

| 字段            | 含义                                 |
| --------------- | ------------------------------------ |
| `fsm_states`    | 传送带运行时允许出现的有限状态集合。 |
| `default_state` | 设备进入仿真运行时的初始状态。       |

| 状态                 | 含义                                     |
| -------------------- | ---------------------------------------- |
| `idle`               | 空闲状态，没有正在输送或等待释放的物料。 |
| `moving`             | 正在输送物料。                           |
| `waiting_downstream` | 物料已到达出口，但下游暂时不能接收。     |
| `blocked`            | 因容量、出口占用或下游不可用导致阻塞。   |
| `error`              | 设备发生异常，无法按当前计划继续运行。   |

### 12.2 资源字段 `resources`

| 字段          | 含义                                                                     |
| ------------- | ------------------------------------------------------------------------ |
| `resources`   | 运行调度资源集合，用于判断行为是否能并发执行、是否需要等待或阻塞。       |
| `resource_id` | 资源 ID。传送带模板中为 `belt_surface`，表示输送面资源。                 |
| `exclusive`   | 是否独占资源。`false` 表示输送面可同时承载多个物料，具体上限由容量控制。 |

`resources` 不是三维几何定义，而是运行时调度契约。它用于回答某个行为执行时需要占用什么资源、资源能否并发使用、资源不足时是否排队或阻塞。

### 12.3 容量字段 `capacity`

| 字段                   | 含义                                                         |
| ---------------------- | ------------------------------------------------------------ |
| `capacity`             | 传送带运行时容量约束。                                       |
| `max_active_materials` | 同一时间可承载或处理的最大物料数量。                         |
| `queue_id`             | 等待队列 ID。传送带模板中为 `stop_point_queue`，表示停留点等待队列。 |
| `resume_threshold`     | 从 blocked 恢复接收的负载阈值。 |

### 12.4 异常策略 `error_policy`

| 字段                    | 含义                                                                   |
| ----------------------- | ---------------------------------------------------------------------- |
| `error_policy`          | 运行异常处理策略集合。                                                 |
| `on_downstream_timeout` | 下游长时间不可用时的处理方式。                                         |
| `emit_observation`      | 表示 Runtime 生成 observation，供 Agent 或诊断模块判断是否需要重规划。 |

## 13. 传送带专属契约 `type_specific_contract`

```json
"type_specific_contract": {
  "conveyor_geometry": {
    "length_m": "长度_required",
    "width_m": "宽度_required",
    "height_m": "高度_optional"
  },
  "motion_model": {
    "type": "linear",
    "axis": [1, 0, 0],
    "speed_param": "speed_mps"
  },
  "stop_point_model": {
    "type": "linear_interpolation",
    "start_interface": "entry",
    "end_interface": "exit",
    "default_stop_point_count": "停留点数量_required",
    "include_entry": true,
    "include_exit": true,
    "coordinate_formula": "entry + t * (exit - entry)",
    "spacing_policy": "evenly_spaced"
  },
  "queue_policy": {
    "when_downstream_busy": "wait_at_nearest_upstream_stop_point",
    "release_on_signal": "release_waiting_material"
  }
}
```

`type_specific_contract` 存放传送带类型特有的信息。通用设备字段描述所有设备都可能拥有的接口、信号和行为；这里描述只有传送带这类设备才需要的几何、运动和排队规则。

### 13.1 几何参数 `conveyor_geometry`

| 字段                | 含义                                                               |
| ------------------- | ------------------------------------------------------------------ |
| `conveyor_geometry` | 传送带几何尺寸信息。                                               |
| `length_m`          | 传送带长度，单位为米。用于计算输送距离，也可辅助前端校准动画范围。 |
| `width_m`           | 传送带宽度，单位为米。用于判断物料适配和可视化占位。               |
| `height_m`          | 传送带高度，单位为米。可选字段，用于接口定位和三维展示。           |

### 13.2 运动模型 `motion_model`

| 字段           | 含义                                                                  |
| -------------- | --------------------------------------------------------------------- |
| `motion_model` | 传送带物料运动模型。                                                  |
| `type`         | 运动类型。`linear` 表示沿直线连续输送。                               |
| `axis`         | 设备局部坐标系下的运动方向向量。`[1, 0, 0]` 表示沿局部 x 正方向运动。 |
| `speed_param`  | 运动速度引用的参数名。这里引用 `params_schema.speed_mps`。            |

`motion_model` 用于计算物料如何从 `entry` 移动到 `exit`，包括运动方向、速度、预计到达时间和前端动画轨迹。

### 13.3 排队策略 `queue_policy`

| 字段                   | 含义                                                              |
| ---------------------- | ----------------------------------------------------------------- |
| `queue_policy`         | 下游不可接收时的等待和释放策略。                                  |
| `when_downstream_busy` | 下游忙碌时的处理方式。`wait_at_nearest_upstream_stop_point` 表示物料停在最靠近下游的上游可用停留点。 |
| `release_on_signal`    | 释放等待物料所需的输入信号。这里使用 `release_waiting_material`。 |

### 13.4 停留点模型 `stop_point_model`

| 字段 | 含义 |
| --- | --- |
| `stop_point_model` | 传送带停留点生成规则。 |
| `type` | 生成方式，第一阶段为 `linear_interpolation`。 |
| `start_interface` | 起点物理接口，通常为 `entry`。 |
| `end_interface` | 终点物理接口，通常为 `exit`。 |
| `default_stop_point_count` | 默认停留点数量，场景实例可覆盖。 |
| `include_entry` | 是否把入口作为第一个停留点。 |
| `include_exit` | 是否把出口作为最后一个停留点。 |
| `coordinate_formula` | 坐标公式，第一阶段为 `entry + t * (exit - entry)`。 |
| `spacing_policy` | 点位间距策略，第一阶段默认 `evenly_spaced`。 |

`stop_point_model` 只定义点位如何生成，不保存当前占用。当前占用应写入 `RuntimeSnapshot.conveyor_occupancy`。

## 14. 字段协作关系

传送带模板中的字段会在运行链路中协同使用。

```text
process_ports        定义工艺层如何连接传送带
interface_bindings   将工艺流程口映射到真实 entry / exit
physical_interfaces  定义物料实际进出位置
transport_behaviors  定义设备能执行哪些输送行为
runtime_contract     定义运行状态、资源占用、容量和异常策略
type_specific_contract.motion_model 定义物料如何运动
type_specific_contract.stop_point_model 定义停留点如何生成
signal_ports         定义到料、阻塞、完成、释放等实时通信信号
```

典型运行过程如下：

```text
1. 上游设备把物料交付到 conveyor.entry。
2. Runtime 检查 capacity 和 resources，判断是否允许执行 accept_material。
3. Runtime 根据 stop_point_model 生成或读取该传送带停留点。
4. 传送带执行 accept_material，将物料放入入口侧可用停留点。
5. Runtime 根据 motion_model 和 stop_point_model 执行 advance_to_next_stop_point。
6. 如果前方停留点或下游忙碌，物料依据 queue_policy 停在最近的上游停留点。
7. 物料到达出口停留点后，传送带输出 part_ready 和 done。
8. 收到 release_waiting_material 或下游可接收后，传送带执行 release_material 并向下游交付物料。
```
