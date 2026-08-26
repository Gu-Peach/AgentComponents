# 2. SceneDocument

`SceneDocument` 是场景事实 schema，记录当前场景中引入了哪些设备本体，以及设备实例之间的流程、物理和信号关系。

## 职责

- 保存场景实例、位姿、参数覆盖和物料实例。
- 保存 `process_edges`、`physical_edges`、`signal_edges` 三类场景关系。
- 作为 `SceneBehaviorGraph` 的场景事实输入。

## 输入与输出

| 项目 | 内容 |
|---|---|
| 上游输入 | 用户搭建场景、选择 DeviceSpec、连接流程口/物理口/信号口。 |
| 输出 | 场景事实文档。 |
| 下游消费者 | SceneBehaviorGraph、Agent、Runtime。 |

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
| `physical_edges` | 真实物理接口连接关系，通常由流程边和接口绑定编译得到。 |
| `signal_edges` | 设备实例之间的信号连接关系。 |
| `runtime_config` | 场景运行配置，例如死锁检测、默认信号超时。 |

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
| `params` | 对设备本体默认参数的场景级覆盖。 |
| `material_id` | 物料实例 ID。 |
| `located_at` | 物料当前初始位置，如设备接口、载具槽位。 |
| `edge_id` | 场景边 ID。 |
| `source` | 边的源端口，如 `conveyor_1.flow_output`。 |
| `target` | 边的目标端口，如 `robot_1.flow_input`。 |
| `edge_type` | 边类型，例如 `material_flow`、`control_signal`。 |
| `compiled_from` | 派生边来源，常用于说明物理边由哪个流程边编译得到。 |

### 规范辅助字段

| Key | 含义 |
|---|---|
| `required_sections` | `SceneDocument` 必须包含的一级字段列表。 |
| `edge_contract` | 三类场景边的职责说明。 |
| `deadlock_detection` | 是否启用死锁检测。 |
| `default_signal_timeout_s` | 默认信号等待超时时间，单位秒。 |
