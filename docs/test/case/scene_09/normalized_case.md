# Scene 09：旋转台定位与机械臂下料 Normalized Case

## case_id

`scene_09_rotary_table_robot_to_workstation`

## source_image

`docs/business/test/9.png`

## raw_description_summary

出料台生成工件，人工搬运简化为旋转台固定工位生成工件；旋转台旋转 90 度后，机械臂抓取工件到工作台，工件消失。

## normalized_user_goal

场景包含物料来源、旋转台、机械臂和工作台。人工搬运步骤第一阶段不建模为独立 actor，而是简化为旋转台 station_a 生成或接收工件。旋转台检测 station_a 有工件后，执行 90 度离散旋转，把工件转到机械臂可达的 station_b。旋转到位后，空闲机械臂抓取工件并放到工作台固定位置。工件到达工作台后离开系统或标记为完成。旋转台工位占用、旋转资源、机械臂资源和工作台占用必须互斥。

## device_inventory

| device_type | instance_id | spec_id | role |
|---|---|---|---|
| `material_source_station` | `source_station_1` | `material_source_station_1` | 物料来源，第一阶段可被旋转台生成替代 |
| `rotary_table` | `rotary_table_1` | `rotary_table_1` | 旋转定位台 |
| `robot_arm` | `robot_1` | `robot_arm_1` | 从旋转台到工作台的搬运机械臂 |
| `material_source_station` | `workstation_1` | `material_source_station_1` | 工作台 / 终点缓存，作为完成位置 |

## material_inventory

- `part_001`
- `part_002`
- `part_003`
- `part_004`

## process_flow_summary

```text
source_station_1/manual feed -> rotary_table_1.station_a -> rotate 90 deg -> rotary_table_1.station_b -> robot_1 -> workstation_1 -> complete
```

## key_runtime_constraints

- 旋转台一次最多处理工位容量内的物料。
- 旋转过程中机械臂不能抓取。
- 工作台占用时机械臂等待。

## assumptions

- 人工搬运不作为独立设备，物料直接在 rotary_table_1.station_a 生成。
- 工作台临时复用 material_source_station_1 的 buffer_area/output 语义，后续可补 workstation DeviceSpec。
- 旋转角度固定为 90 度。

## open_questions

- 工作台是否需要独立 DeviceSpec？
- 旋转台是否有多个工件并行工位？
