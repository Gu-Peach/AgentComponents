# robot_arm template 字段说明

本文用于解释 `robot_arm/template.json` 中每个板块和字段的含义，作为后续编写机械臂类 `DeviceSpec` 的填写说明。

## 1. 模板定位

`robot_arm/template.json` 是机械臂设备本体的填写模板，描述机械臂的资产、参数、接口、信号、抓取搬运行为、运行契约，以及驱动器需要的 `urdf.joints` 和 `trajectoryConfig` 运动配置。

场景中不会直接复制该模板运行，而是先填写成具体 `DeviceSpec`，再由 `SceneDocument.instances[].spec_id` 引用。

## 2. 占位符规则

| 后缀 | 含义 |
| --- | --- |
| `_required` | 必填字段，具体设备规范中必须替换为真实值。 |
| `_optional` | 可选字段，可填写、留空或由系统推断。 |
| `a|b|required` | 枚举值提示，表示应从候选语义中选择真实值。 |
| `{file}` | 文件名占位符，需要替换为具体 GLB 文件名。 |

## 3. 通用元信息

| 字段 | 含义 |
| --- | --- |
| `schema_id` | 当前模板文件的唯一标识。 |
| `schema_type` | 当前 JSON 类型；这里是 `DeviceSpecTemplate`。 |
| `version` | 模板版本。 |
| `name` | 模板展示名称。 |
| `description` | 模板用途说明，强调机械臂需保留驱动器标准字段。 |
| `source.kind` | 模板来源类型；`manual_template` 表示人工设计模板。 |
| `source.path` | 当前模板路径。 |
| `created_for` | 模板服务的设备建模对象。 |
| `references` | 依赖的通用设备规范、类型规范和示例文件。 |
| `notes` | 填写注意事项，尤其是 `urdf.joints` 与 `trajectoryConfig`。 |

## 4. 设备标识

| 字段 | 含义 |
| --- | --- |
| `device_spec_id` | 机械臂设备本体规范 ID，供场景实例引用。 |
| `device_type` | 设备类型，机械臂固定为 `robot_arm`。 |
| `display_name` | 前端、文档和日志中展示的设备名称。 |

## 5. 资产信息 `asset`

| 字段 | 含义 |
| --- | --- |
| `model_format` | 三维模型格式，当前阶段通常为 `glb`。 |
| `model_key` | GLB 模型资源路径或对象存储 key。 |
| `root_node_name` | 机械臂模型根节点名，用于驱动器定位关节层级。 |

`asset` 只负责模型加载定位；真实行为能力由接口、行为和类型专属契约共同描述。

## 6. 参数定义 `params_schema`

| 字段 | 含义 |
| --- | --- |
| `params_schema` | 机械臂可配置参数集合，场景实例可在此基础上覆盖。 |
| `speed` | 机械臂默认运行速度，用于抓取搬运或轨迹规划。 |
| `speed.type` | 参数类型，`number` 表示数值。 |
| `speed.default` | 默认速度，必填。 |
| `speed.min` / `speed.max` | 可选速度上下限。 |
| `speed.unit` | 速度单位。 |
| `payload_kg` | 额定或默认负载，单位 kg。 |
| `payload_kg.min` / `payload_kg.max` | 负载上下限，用于校验物料是否可抓取。 |
| `lift_height` | 抓取搬运过程中的默认抬升高度。 |

## 7. 物理接口 `physical_interfaces`

`physical_interfaces` 描述机械臂与物料发生真实交互的位置或工具点。

| 字段 | 含义 |
| --- | --- |
| `interface_id` | 物理接口 ID。 |
| `kind` | 接口类型；`material` 表示物料交接，`tool` 表示工具中心点。 |
| `direction` | 接口方向；`input` 入料，`output` 出料，`bidirectional` 双向。 |
| `node_name` | GLB 模型中的锚点节点名。 |
| `material_classes` | 支持交互的物料类型。 |
| `local_position` | 可选局部坐标，用于定位接口。 |
| `local_forward` | 可选局部朝向，用于判断抓取或放置方向。 |

| 接口 | 含义 |
| --- | --- |
| `pick_area` | 抓取区域，作为物料输入位置。 |
| `place_area` | 放置区域，作为物料输出位置。 |
| `tool_center_point` | 工具中心点 / TCP，描述夹爪或末端执行器的位置。 |

## 8. 工艺流程口 `process_ports`

| 字段 | 含义 |
| --- | --- |
| `port_id` | 工艺流程口 ID。 |
| `direction` | 工艺方向。 |
| `label` | 流程画布展示名称。 |

| 流程口 | 含义 |
| --- | --- |
| `flow_input` | 机械臂抓取侧的工艺输入。 |
| `flow_output` | 机械臂放置侧的工艺输出。 |

## 9. 信号端口 `signal_ports`

| 信号 | 方向 | 类型 | 含义 |
| --- | --- | --- | --- |
| `start_pick` | `input` | `event` | 触发机械臂开始抓取搬运动作。 |
| `busy` | `output` | `boolean` | 机械臂正在执行动作。 |
| `done` | `output` | `event` | 当前抓取搬运动作完成。 |
| `error` | `output` | `event` | 当前动作失败或设备异常。 |

## 10. 接口绑定 `interface_bindings`

| 绑定关系 | 含义 |
| --- | --- |
| `flow_input -> pick_area` | 工艺输入映射到真实抓取区域。 |
| `flow_output -> place_area` | 工艺输出映射到真实放置区域。 |

## 11. 输送行为 `transport_behaviors`

`transport_behaviors` 描述机械臂可被计划和 Runtime 调用的行为能力。

| 字段 | 含义 |
| --- | --- |
| `behavior_id` | 行为 ID；模板中核心行为为 `pick_and_place`。 |
| `behavior_type` | 行为类型；`material_transfer` 表示物料转移。 |
| `input_physical_interface` | 行为输入接口，即抓取位置。 |
| `output_physical_interface` | 行为输出接口，即放置位置。 |
| `default_algorithm` | 默认执行算法；机械臂为 `robot_pick_place`。 |
| `input_signals` | 启动行为所需信号。 |
| `output_signals` | 行为过程中或完成后输出的信号。 |
| `resources` | 行为需要占用的运行资源。 |
| `preconditions` | 行为启动前必须满足的条件。 |
| `effects` | 行为执行完成后对物料位置和信号产生的影响。 |

## 12. 运行契约 `runtime_contract`

| 字段 | 含义 |
| --- | --- |
| `fsm_states` | 机械臂运行时状态集合。 |
| `default_state` | 初始状态。 |
| `resources` | 调度资源集合，用于互斥和并发控制。 |
| `capacity.max_active_materials` | 同一时间可处理的物料数量，机械臂通常为 1。 |
| `error_policy` | 超时、目标不可达等异常策略。 |

| 状态 | 含义 |
| --- | --- |
| `idle` | 空闲，可接收任务。 |
| `busy` | 正在执行抓取搬运。 |
| `waiting` | 等待物料、信号或资源。 |
| `error` | 动作异常或设备异常。 |

| 资源 | 含义 |
| --- | --- |
| `robot_arm` | 机械臂本体运动资源，通常独占。 |
| `gripper` | 夹爪资源，通常独占。 |

## 13. 机械臂专属契约 `type_specific_contract`

| 字段 | 含义 |
| --- | --- |
| `rootNodeName` | 模型根节点名，驱动器据此定位机械臂模型层级。 |
| `urdf.joints` | 关节定义列表，是机械臂驱动和运动计算的核心结构。 |
| `trajectoryConfig` | 轨迹执行配置，保留驱动器标准格式。 |
| `workspace` | 工作空间约束，可用于判断目标是否可达。 |
| `gripper` | 夹爪配置，包括类型、支持物料和最大负载。 |

### `urdf.joints[]`

| 字段 | 含义 |
| --- | --- |
| `name` | 关节名称。 |
| `nodeName` | GLB 中对应关节节点名。 |
| `type` | 关节类型，例如 `revolute`。 |
| `axis.x/y/z` | 关节旋转或移动轴。 |
| `limit.lower` / `limit.upper` | 关节运动上下限。 |

### `trajectoryConfig`

| 字段 | 含义 |
| --- | --- |
| `liftHeight` | 抓取后抬升高度。 |
| `speed` | 轨迹执行速度。 |

## 14. 字段协作关系

```text
process_ports / interface_bindings  定义工艺输入输出如何映射到抓取/放置位置
physical_interfaces                 定义真实抓取区域、放置区域和 TCP
signal_ports                        定义 start_pick、busy、done、error 通讯
transport_behaviors                 定义 pick_and_place 行为
runtime_contract.resources          保证机械臂和夹爪互斥占用
type_specific_contract.urdf         支撑关节级驱动和运动仿真
```

