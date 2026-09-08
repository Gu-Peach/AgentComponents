# 2. SceneDocument

`SceneDocument` 是场景事实 schema，记录当前场景中引入了哪些设备本体，以及设备实例之间的流程、物理和信号关系。

## 职责

- 保存场景实例、位姿、参数覆盖和物料实例。
- 保存 `process_edges`、`physical_edges`、`signal_edges` 三类场景关系。
- 可记录 `derived_artifacts.topology_graph` 引用，但派生拓扑图不是手工事实源。
- 为传送带实例设置 `stop_point_count`、`capacity`、`resume_threshold` 等场景级参数覆盖。
- 作为 `SceneBehaviorGraph` 的场景事实输入。

## 输入与输出

| 项目 | 内容 |
|---|---|
| 上游输入 | 用户搭建场景、选择 DeviceSpec、连接流程口/物理口/信号口。 |
| 输出 | 场景事实文档。 |
| 下游消费者 | TopologyGraph compiler、SceneBehaviorGraph、Agent、Runtime。 |

## Key 含义

### 通用元信息

| Key | 含义 |
|---|---|
| `schema_id` | 当前场景文档示例或规范的唯一标识。 |
| `schema_type` | JSON 类型；场景事实示例使用 `SceneDocument`。 |
| `version` | 规范版本。 |
| `name` | 场景文档名称。 |
| `description` | 场景文档用途说明。 |
| `source` | 场景来源，例如图片推断、前端保存或人工示例。 |
| `created_for` | 该场景文档服务的示例或仿真目标。 |
| `references` | 引用的设备本体、图片或上游规范。 |
| `notes` | 场景事实边界和设计备注。 |

### 场景事实字段

| Key | 含义 |
|---|---|
| `scene_id` | 场景唯一 ID。 |
| `revision` | 场景修订号，每次结构变化递增。 |
| `instances` | 当前场景引入的设备实例列表。 |
| `materials` | 当前场景中的物料实例列表。 |
| `process_edges` | 工艺流程关系，描述 `flow_output -> flow_input`。 |
| `physical_edges` | 真实物理接口连接关系，用于设备/模型几何对齐、吸附、挂载或装配；不表示物料流。 |
| `signal_edges` | 设备实例之间的信号连接关系。 |
| `runtime_config` | 场景运行配置，例如死锁检测、默认信号超时。 |
| `derived_artifacts` | 推荐字段，记录 topology_graph 等派生产物引用和编译状态。 |

### 常见嵌套字段

| Key | 含义 |
|---|---|
| `instance_id` | 场景中设备实例 ID。 |
| `spec_id` | 引用的设备本体 `DeviceSpec.device_spec_id`。 |
| `device_type` | 设备类型，用于筛选和校验。 |
| `transform` | 设备实例在三维场景中的位姿。 |
| `position` | 实例位置 `[x, y, z]`。 |
| `rotation_euler` | 实例欧拉角旋转。 |
| `scale` | 实例缩放。 |
| `param_overrides` | 对设备本体默认参数的场景级覆盖，推荐新字段。 |
| `params` | `param_overrides` 的旧别名，兼容早期示例。 |
| `runtime_geometry` | 当前场景实例的执行几何，坐标已经落到 scene/world 坐标。 |
| `runtime_kinematics` | 当前场景实例的运行时运动结构，例如机械臂 IK chain、joint nodeName、TCP。 |
| `asset_binding` | 当前实例绑定到 GLB/场景资产中的节点信息。 |
| `material_id` | 物料实例 ID。 |
| `located_at` | 物料当前初始位置，如设备接口、载具槽位。 |
| `edge_id` | 场景边 ID。 |
| `source` | 边的源端口，如 `conveyor_1.flow_output`。 |
| `target` | 边的目标端口，如 `robot_1.flow_input`。 |
| `edge_type` | 边类型，例如 `material_flow`、`control_signal`。 |
| `compiled_from` | 派生边来源，常用于说明物理边由哪个流程边编译得到。 |
| `delivery` | 信号边投递方式，例如 `event`、`latest_value`、`command`、`broadcast`。 |
| `trigger` | 信号边触发方式，例如 `on_rising_edge`、`on_change`、`level`。 |
| `transform` | 信号 payload 转换方式，例如 `identity`、`payload_template`、`expression`。 |
| `timeout_ms` | 信号投递或等待超时时间。 |
| `on_timeout` | 超时处理策略，例如 `raise_observation`、`retry`、`pause_and_request_replan`。 |

### 规范辅助字段

| Key | 含义 |
|---|---|
| `required_sections` | `SceneDocument` 必须包含的一级字段列表。 |
| `edge_contract` | 三类场景边的职责说明。 |
| `process_edge_contract` | 工艺边端口格式、方向和校验规则。 |
| `physical_edge_contract` | 物理边接口格式、兼容性和吸附校验规则。 |
| `signal_edge_contract` | 信号边投递、触发、转换和超时规则。 |
| `derived_artifacts_contract` | topology_graph 等派生产物的引用和失效规则。 |
| `deadlock_detection` | 是否启用死锁检测。 |
| `default_signal_timeout_s` | 默认信号等待超时时间，单位秒。 |

### 传送带实例参数覆盖

| Key | 含义 |
|---|---|
| `param_overrides.stop_point_count` | 当前传送带实例生成多少个停留点。Runtime 根据 entry/exit 坐标线性插值。 |
| `param_overrides.stop_point_spacing_policy` | 停留点分布方式，第一阶段默认 `evenly_spaced`。 |
| `param_overrides.capacity` | 当前传送带实例可同时承载的物料或载具数量。 |
| `param_overrides.resume_threshold` | blocked 后恢复接收的负载阈值。 |

## 运行时实例数据

`DeviceSpec` 只描述设备本体的局部默认能力，例如 `process_ports.local_frame`、机械臂 `urdf.joints`、默认轨迹参数。设备被拖入场景后，编译器或前端校准器应把运行时需要直接读取的数据写入 `SceneDocument.instances[]`。

| 字段 | 运行时含义 |
|---|---|
| `runtime_geometry.transport_path` | 传送带实例的 scene 坐标输送路径、停留点和起止工艺口。 |
| `runtime_geometry.process_points` | 设备实例各工艺口在当前场景中的 scene 坐标。 |
| `runtime_geometry.pick_place_path` | 机械臂抓取/放置动作的 scene 坐标 pick/place 点和路径。 |
| `runtime_kinematics.kinematic_chain` | 机械臂实例的 IK chain 快照，由 DeviceSpec URDF 和 GLB 节点绑定编译而来。 |

运行时播放动画时优先读取 `SceneDocument.instances[].runtime_geometry` 和 `runtime_kinematics`；只有编译/校准阶段才回到 `DeviceSpec` 读取局部默认定义。
