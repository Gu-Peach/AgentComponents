# Scene 05：圆桌双机械臂多出料分拣 Normalized Case

## case_id

`scene_05_round_table_dual_robot_dispatch`

## source_image

`docs/business/test/5.png`

## raw_description_summary

圆桌固定位置生成物料，两台机械臂从圆桌取料并放到空闲出料传送带，多个出料传送带按停留点容量接收物料。

## normalized_user_goal

圆桌中心作为物料呈现区域，物料由人工上料过程简化为 Runtime 在圆桌固定位置生成。两台机械臂监控圆桌上的待处理物料，谁空闲谁 claim 一个物料，并根据出料传送带容量选择空闲或负载较低的目标传送带。目标传送带入口停留点可用时，机械臂执行 pick_and_place；如果某条传送带 blocked，则该传送带不参与目标选择。所有出料传送带都必须按停留点推进和释放。

## device_inventory

| device_type | instance_id | spec_id | role |
|---|---|---|---|
| `rotary_table` | `round_table_1` | `rotary_table_1` | 圆桌 / 物料呈现台 |
| `robot_arm` | `robot_1` | `robot_arm_1` | 圆桌分拣机械臂 1 |
| `robot_arm` | `robot_2` | `robot_arm_1` | 圆桌分拣机械臂 2 |
| `conveyor` | `out_conveyor_1` | `conveyor_1` | 出料传送带 1 |
| `conveyor` | `out_conveyor_2` | `conveyor_1` | 出料传送带 2 |
| `conveyor` | `out_conveyor_3` | `conveyor_1` | 出料传送带 3 |
| `conveyor` | `out_conveyor_4` | `conveyor_1` | 出料传送带 4 |

## material_inventory

- `part_001`
- `part_002`
- `part_003`
- `part_004`
- `part_005`
- `part_006`
- `part_007`
- `part_008`

## process_flow_summary

```text
round_table_1.station_a generated material -> robot_1 / robot_2 claim -> least-loaded available output conveyor -> exit
```

## key_runtime_constraints

- 圆桌呈现位一次只能被有限物料占用。
- 两台机械臂共享圆桌工件池。
- 目标出料传送带选择必须排除 blocked 传送带。

## assumptions

- 工人上料简化为 round_table_1.station_a 的物料生成事件。
- 圆桌不必持续旋转，作为固定呈现台使用；后续可扩展 rotary indexing。

## open_questions

- 不同出料传送带是否代表不同类别？
- 圆桌是否需要真实旋转节拍？
