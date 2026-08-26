# 1. DeviceSpec

`DeviceSpec` 是设备本体行为模型，定义一类设备本身具备的参数、资产、接口、信号、行为能力、运行契约和设备特殊运动特性。

## 职责

- 作为设备库中的标准设备本体定义。
- 为 `SceneDocument.instances` 提供可实例化引用。
- 为 `SceneBehaviorGraph` 的 Agent 建模和 Runtime 执行提供设备能力约束。

## 输入与输出

| 项目 | 内容 |
|---|---|
| 上游输入 | 设备几何资产、驱动器约束、接口定义、行为能力定义。 |
| 输出 | 可被场景引用的设备本体 JSON。 |
| 下游消费者 | SceneDocument、SceneBehaviorGraph、Agent、Runtime。 |

## 文件说明

- `schema.json`：DeviceSpec 板块级规范，说明 DeviceSpec 环节整体职责。
- `common_device_spec.schema.json`：所有设备本体必须遵守的通用设备基类规范。
- `template.json`：所有设备本体的通用填写模板，标注哪些字段必填、哪些字段可选。
- `example.json`：DeviceSpec 最小通用示例。
- `{device_type}/schema.json`：某类设备的专属规范。
- `{device_type}/template.json`：某类设备的专属填写模板，后续新增同类设备时优先复制该模板。
- `{device_type}/{device_instance}.json`：该类型下的具体设备本体示例。

## 设备分类目录

| 目录 | 设备类型 | 示例文件 |
|---|---|---|
| `robot_arm/` | 机械臂 | `schema.json`、`template.json`、`robot_arm_1.json` |
| `conveyor/` | 传送带 | `schema.json`、`template.json`、`conveyor_1.json` |
| `workpiece/` | 物料 / 工件 | `schema.json`、`template.json`、`workpiece_1.json` |
| `workpiece_carrier/` | 物料载具 / 承载托盘 | `schema.json`、`template.json`、`carrier_tray_1.json` |
| `material_source_station/` | 物料生产 / 上料台 | `schema.json`、`template.json`、`material_source_station_1.json` |
| `lift_table/` | 升降台 | `schema.json`、`template.json`、`lift_table_1.json` |
| `storage_rack/` | 存储柜 / 货架 | `schema.json`、`template.json`、`storage_rack_1.json` |
| `rotary_table/` | 旋转台 | `schema.json`、`template.json`、`rotary_table_1.json` |

## 规范、模板、示例的区别

| 文件 | 用途 | 是否用于后续撰写 |
|---|---|---|
| `schema.json` | 定义该层或该设备类型的规范约束，说明应该有哪些 section 和能力。 | 用于校验和理解，不建议直接复制填写。 |
| `template.json` | 给设备建模者使用的填写模板，标注 required / optional / inferred_from_example。 | 后续新增设备时优先复制。 |
| `*_1.json` | 基于当前图片和已有案例整理出的具体设备本体示例。 | 用于参考，不代表所有设备都一样。 |

模板中的占位值约定：

```text
*_required              必须填写，不能留空。
*_optional              可选字段，没有信息时可以省略或使用默认策略。
*_inferred_from_example 可根据图片、GLB 节点、已有驱动配置或示例设备推断后填写。
```

因此后续新增设备的推荐流程是：

```text
1. 先进入对应设备类型目录。
2. 复制该目录下的 template.json。
3. 按 required / optional 标记填写真实值。
4. 参考同目录的 *_1.json 校准字段写法。
5. 用 schema.json 检查该设备是否满足类型规范。
```

## `schema.json` 与 `common_device_spec.schema.json` 的区别

这两个文件处在不同层级，容易混淆：

```text
schema.json
  = DeviceSpec 目录/板块级规范
  = 说明 DeviceSpec 作为当前基线设备能力板块，整体负责什么、包含哪些 section、服务哪些下游环节。

common_device_spec.schema.json
  = 具体设备本体的通用基类规范
  = 说明 robot_arm_1.json、conveyor_1.json、workpiece_1.json 等具体设备文件都必须遵守哪些共同字段。
```

更具体地说：

| 文件 | 关注对象 | 回答的问题 | 类比 |
|---|---|---|---|
| `schema.json` | `DeviceSpec` 这个 schema 板块 | DeviceSpec 这个环节负责什么？它有哪些 section？它和 SceneDocument / SceneBehaviorGraph / Agent / Runtime 是什么关系？ | DeviceSpec 板块说明书 |
| `common_device_spec.schema.json` | 每一个具体设备本体 JSON | 所有设备文件都必须有哪些字段？哪些字段是通用的？哪些字段允许被设备类型扩展？ | 设备本体基类 / 设备 JSON 通用模板 |

层级关系如下：

```text
../common_schema_contract.json
  所有 JSON 都要遵守的元信息规范

schema.json
  DeviceSpec 作为当前基线设备能力板块的模块规范

common_device_spec.schema.json
  所有具体设备本体的通用结构规范

{device_type}/schema.json
  某一类设备的专属规范，例如 robot_arm/schema.json、conveyor/schema.json

{device_type}/{device_instance}.json
  某一个设备本体示例，例如 robot_arm/robot_arm_1.json、conveyor/conveyor_1.json
```

继承/引用关系可以理解为：

```text
common_device_spec.schema.json
  -> robot_arm/schema.json
      -> robot_arm_1.json

common_device_spec.schema.json
  -> conveyor/schema.json
      -> conveyor_1.json

common_device_spec.schema.json
  -> storage_rack/schema.json
      -> storage_rack_1.json
```

如果后续觉得命名还不够直观，可以考虑把：

```text
schema.json -> device_spec_module.schema.json
common_device_spec.schema.json -> base_device_spec.schema.json
```

当前阶段先保留现有命名，但以上层级解释作为使用准则。

## Key 含义

### 通用元信息

| Key | 含义 |
|---|---|
| `schema_id` | 当前设备规范或设备示例的唯一标识。 |
| `schema_type` | JSON 类型；设备示例统一为 `DeviceSpec`，设备类型规范为 `DeviceTypeSchema`。 |
| `version` | 规范版本。 |
| `name` | 设备或规范的人类可读名称。 |
| `description` | 设备能力或规范用途说明。 |
| `source` | 数据来源，例如图片推断、人工设计、驱动器配置。 |
| `created_for` | 该设备规范服务的场景、图片或研究目标。 |
| `references` | 参考的设备类型规范、图片或文档。 |
| `notes` | 设计备注和边界说明。 |

### 设备本体字段

| Key | 含义 |
|---|---|
| `id` | 可选兼容字段，保留旧设备配置中的设备 ID。 |
| `device_spec_id` | 设备本体 ID，供 `SceneDocument.instances[].spec_id` 引用。 |
| `device_type` | 设备类型，例如 `robot_arm`、`conveyor`、`storage_rack`。 |
| `display_name` | 前端或文档中展示的设备名称。 |
| `asset` | 设备三维资产引用，如 GLB 路径、模型格式、根节点。 |
| `params_schema` | 设备可配置参数定义，包括默认值、范围和单位。 |
| `physical_interfaces` | 真实空间中的物理接口、抓取区、放置区、入口、出口等锚点。 |
| `process_ports` | 工艺流程画布使用的抽象入口/出口。 |
| `signal_ports` | 设备可接收或发出的运行时信号。 |
| `interface_bindings` | `process_ports` 到 `physical_interfaces` 的绑定关系。 |
| `transport_behaviors` | 设备本体支持的物料流转行为能力。 |
| `runtime_contract` | FSM 状态、资源、容量和错误策略等运行契约。 |
| `type_specific_contract` | 设备类型专属能力，例如机械臂关节、传送带运动模型、货架库位。 |

### 常见嵌套字段

| Key | 含义 |
|---|---|
| `interface_id` | 物理接口唯一 ID。 |
| `kind` | 接口类别，例如 `material`、`tool`、`support`、`storage`。 |
| `direction` | 接口方向，常见为 `input`、`output`、`bidirectional`。 |
| `node_name` | GLB/场景节点名，用于把接口锚定到模型节点。 |
| `material_classes` | 该接口支持的物料类型。 |
| `local_position` | 接口在设备局部坐标系中的位置。 |
| `local_forward` | 接口在设备局部坐标系中的朝向。 |
| `port_id` | 流程口或信号口 ID。 |
| `value_type` | 信号值类型，例如 `event`、`boolean`、`command`。 |
| `behavior_id` | 设备行为能力 ID。 |
| `behavior_type` | 行为类别，例如 `material_transfer`、`continuous_transport`、`rotary_motion`。 |
| `input_physical_interface` | 行为使用的输入物理接口。 |
| `output_physical_interface` | 行为使用的输出物理接口。 |
| `input_signals` | 启动或控制行为所需的输入信号。 |
| `output_signals` | 行为执行中或完成后发出的信号。 |
| `preconditions` | 行为启动前必须满足的条件。 |
| `effects` | 行为完成后对物料位置、信号或状态造成的结果。 |
| `fsm_states` | 设备运行状态集合。 |
| `default_state` | 设备实例初始化时的默认状态。 |
| `resources` | 行为执行时会占用的设备资源。 |
| `capacity` | 设备可同时承载、处理或存储的物料数量约束。 |
| `error_policy` | 超时、不可达、阻塞等异常时的处理策略。 |

### 规范辅助字段

| Key | 含义 |
|---|---|
| `required_sections` | `DeviceSpec` 必须包含的一级业务字段列表。 |
| `section_contract` | 每个一级业务字段的职责说明。 |
| `required_common_device_fields` | 所有设备本体必须包含的通用字段列表。 |
| `field_contract` | 通用设备字段的含义说明。 |
| `extends` | 当前设备类型规范继承的通用规范 ID。 |
| `required_type_specific_fields` | 某类设备必须补充的类型专属字段。 |
| `required_behaviors` | 某类设备必须具备的行为能力。 |
| `required_signals` | 某类设备必须具备的信号口。 |

### 设备特殊字段

| Key | 含义 |
|---|---|
| `rootNodeName` | 机械臂驱动器使用的模型根节点名，保留现有驱动配置格式。 |
| `urdf` | 机械臂关节和运动链配置容器。 |
| `joints` | 机械臂关节列表。 |
| `nodeName` | 关节对应的 GLB 节点名，保留驱动器原字段格式。 |
| `axis` | 关节或运动轴向量。 |
| `x` / `y` / `z` | 三维向量分量。 |
| `limit` | 关节运动限制。 |
| `lower` / `upper` | 关节下限和上限。 |
| `trajectoryConfig` | 机械臂轨迹配置，保留现有驱动器标准格式。 |
| `liftHeight` | 机械臂抓取搬运时的抬升高度。 |
| `speed` | 机械臂轨迹默认速度。 |
| `workspace` | 机械臂工作空间描述。 |
| `gripper` | 夹爪能力描述。 |
| `conveyor_geometry` | 传送带几何尺寸。 |
| `motion_model` | 传送带、升降台或旋转台的运动模型。 |
| `queue_policy` | 下游阻塞时的等待/释放策略。 |
| `geometry` | 物料几何描述。 |
| `grasping` | 物料可抓取面和抓取偏好。 |
| `placement` | 物料可放置面和稳定性约束。 |
| `carrier_geometry` | 物料载具几何尺寸。 |
| `slots` | 载具槽位布局。 |
| `load_policy` | 载具可承载物料类型和装载规则。 |
| `production_policy` | 物料来源工位的生产/上料策略。 |
| `buffer` | 物料来源工位的缓存区约束。 |
| `output_material_spec` | 物料来源工位产出的物料本体 ID。 |
| `height_levels` | 升降台可对接高度列表。 |
| `lift_motion` | 升降台运动轴、速度参数等配置。 |
| `dock_policy` | 升降台与上下游接口对接规则。 |
| `cells` | 存储柜库位定义。 |
| `reservation_policy` | 存储柜库位预约策略。 |
| `stations` | 旋转台工位定义。 |
| `rotation_axis` | 旋转台旋转轴。 |
| `indexing_policy` | 旋转台离散定位策略。 |
| `rows` / `columns` | 槽位、库位的行列数量。 |
| `level_id` / `station_id` | 高度层或旋转工位 ID。 |
| `angle_deg` | 旋转工位角度。 |
| `height_m` / `length_m` / `width_m` / `diameter_m` / `radius_m` | 几何尺寸字段，单位为米。 |
| `min` / `max` / `default` / `unit` | 参数范围、默认值和单位说明。 |
