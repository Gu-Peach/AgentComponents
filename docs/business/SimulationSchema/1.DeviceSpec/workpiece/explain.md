# workpiece template 字段说明

本文用于解释 `workpiece/template.json` 中每个板块和字段的含义，作为后续编写物料 / 工件类 `DeviceSpec` 的填写说明。

## 1. 模板定位

`workpiece` 是被设备搬运、承载、存储或加工的被动对象。它通常不主动执行 `transport_behaviors`，但需要定义尺寸、质量、抓取面、放置面和运行状态，以便机械臂、传送带、载具、升降台等设备判断能否操作它。

## 2. 占位符规则

| 后缀 | 含义 |
| --- | --- |
| `_required` | 必填字段，具体物料规范中必须替换。 |
| `_optional` | 可选字段，可填写或留空。 |
| `{file}` | 资产文件名占位符。 |

## 3. 通用元信息

| 字段 | 含义 |
| --- | --- |
| `schema_id` | 当前模板唯一标识。 |
| `schema_type` | JSON 类型；这里是 `DeviceSpecTemplate`。 |
| `version` | 模板版本。 |
| `name` | 模板展示名称。 |
| `description` | 模板用途说明。 |
| `source.kind` / `source.path` | 模板来源类型和路径。 |
| `created_for` | 模板服务的设备本体类型。 |
| `references` | 依赖的通用规范、类型规范和示例。 |
| `notes` | 说明物料通常是被动对象，行为列表可为空。 |

## 4. 设备标识

| 字段 | 含义 |
| --- | --- |
| `device_spec_id` | 物料本体规范 ID。 |
| `device_type` | 设备类型，物料固定为 `workpiece`。 |
| `display_name` | 展示名称。 |

## 5. 资产信息 `asset`

| 字段 | 含义 |
| --- | --- |
| `model_format` | 模型格式；物料资产可选，通常为 `glb`。 |
| `model_key` | 物料模型路径或对象存储 key。 |

## 6. 参数定义 `params_schema`

| 字段 | 含义 |
| --- | --- |
| `params_schema` | 物料可配置参数集合。 |
| `mass_kg` | 物料质量，单位 kg，可用于机械臂负载校验。 |
| `mass_kg.type` | 参数类型。 |
| `mass_kg.default` | 默认质量，可选。 |
| `mass_kg.unit` | 参数单位。 |

## 7. 物理接口 `physical_interfaces`

| 接口 | 类型 | 方向 | 含义 |
| --- | --- | --- | --- |
| `grasp_surface` | `grasp` | `bidirectional` | 物料可被夹爪抓取的区域或表面。 |
| `bottom` | `support` | `input` | 物料稳定放置的底面。 |

| 字段 | 含义 |
| --- | --- |
| `interface_id` | 接口 ID。 |
| `kind` | 接口类型，如抓取面或支撑面。 |
| `direction` | 接口方向。 |
| `node_name` | GLB 模型中的锚点节点名，可选。 |
| `material_classes` | 该接口所属或支持的物料类别。 |

## 8. 工艺流程口 `process_ports`

物料模板中 `process_ports` 为空，表示物料自身不作为主动工艺设备提供流程入口或出口。物料在工艺中的流转由承载它的设备、载具和场景级 `materials.located_at` 描述。

## 9. 信号端口 `signal_ports`

| 信号 | 方向 | 类型 | 含义 |
| --- | --- | --- | --- |
| `picked` | `output` | `event` | 物料被抓取后可产生的事件。 |
| `placed` | `output` | `event` | 物料被放置后可产生的事件。 |

物料信号通常由 Runtime 或操作设备代为触发，用于记录物料状态变化。

## 10. 接口绑定 `interface_bindings`

物料模板中 `interface_bindings` 为空，因为物料不是主动流程设备，不需要把工艺流程口映射到物理接口。

## 11. 输送行为 `transport_behaviors`

物料模板中 `transport_behaviors` 为空。物料本体主要描述“可被如何操作”，主动搬运、输送、存储行为由机械臂、传送带、载具、升降台等设备提供。

## 12. 运行契约 `runtime_contract`

| 字段 | 含义 |
| --- | --- |
| `fsm_states` | 物料运行时位置/占用状态集合。 |
| `default_state` | 初始状态。 |
| `resources` | 物料自身不主动占用调度资源，因此通常为空。 |
| `capacity.max_active_materials` | 物料不是容器，通常为 0。 |

| 状态 | 含义 |
| --- | --- |
| `free` | 未被抓取或绑定到设备动作。 |
| `carried` | 正被机械臂、载具或其他设备搬运。 |
| `placed` | 已放置在某个接口、载具或库位。 |

## 13. 物料专属契约 `type_specific_contract`

| 字段 | 含义 |
| --- | --- |
| `material_class` | 物料类别，用于接口兼容和设备能力匹配。 |
| `geometry` | 物料几何信息。 |
| `grasping` | 抓取规则和偏好。 |
| `placement` | 放置稳定性规则。 |

### `geometry`

| 字段 | 含义 |
| --- | --- |
| `shape` | 几何形状，必填。 |
| `diameter_m` | 直径，适合圆柱或圆形物料。 |
| `height_m` | 高度。 |
| `length_m` | 长度。 |
| `width_m` | 宽度。 |

### `grasping`

| 字段 | 含义 |
| --- | --- |
| `allowed_grasp_interfaces` | 允许抓取的接口列表。 |
| `preferred_grasp` | 首选抓取方式或抓取面，可选。 |

### `placement`

| 字段 | 含义 |
| --- | --- |
| `stable_surfaces` | 可稳定放置的表面列表。 |
| `can_stack` | 是否允许堆叠，可选。 |

## 14. 字段协作关系

```text
geometry / mass_kg       用于设备兼容性和负载校验
grasp_surface            用于机械臂抓取判断
bottom / stable_surfaces 用于放置稳定性判断
picked / placed          用于运行时记录物料状态变化
located_at               在 SceneDocument 中记录物料实例当前位置
```

