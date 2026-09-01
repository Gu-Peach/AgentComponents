# Scene 08：物料与托盘同步到位装载 Normalized Case

## case_id

`scene_08_synchronized_part_to_pallet_loading`

## source_image

`docs/business/test/8.png`

## raw_description_summary

物料侧出料台和传送带持续送料，托盘侧传送带同步运输空托盘；当物料和托盘都到位时，机械臂把物料装到托盘，达到数量后托盘输出。

## normalized_user_goal

场景包含物料出料台、物料侧传送带、托盘、托盘侧传送带和一台机械臂。物料出料台持续输出工件，工件进入物料传送带并按停留点排队。空托盘进入托盘传送带并移动到装载位置。当物料传送带出口有工件且托盘位到达装载位置时，机械臂抓取工件并放入托盘空槽。装载过程中，后续物料和托盘必须停在各自传送带上游停留点等待。托盘达到目标装载数量后，托盘传送带继续将该托盘运输到出口并离开系统，后续空托盘补位。

## device_inventory

| device_type | instance_id | spec_id | role |
|---|---|---|---|
| `material_source_station` | `part_source_1` | `material_source_station_1` | 物料出料台 |
| `conveyor` | `part_conveyor_1` | `conveyor_1` | 物料侧传送带 |
| `conveyor` | `pallet_conveyor_1` | `conveyor_1` | 托盘侧传送带 |
| `robot_arm` | `robot_1` | `robot_arm_1` | 装托盘机械臂 |
| `workpiece_carrier` | `pallet_1` | `carrier_tray_1` | 待装载托盘 |

## material_inventory

- `part_001`
- `part_002`
- `part_003`
- `part_004`
- `part_005`
- `part_006`
- `part_007`
- `part_008`
- `part_009`
- `part_010`
- `part_011`
- `part_012`

## process_flow_summary

```text
part_source_1 -> part_conveyor_1 stop points + pallet_conveyor_1 stop points -> synchronized loading by robot_1 -> loaded pallet exits
```

## key_runtime_constraints

- 物料到位和托盘到位必须同时满足才能抓取。
- 托盘目标装载数达到后才可输出。
- 两个传送带都必须按停留点排队等待。

## assumptions

- 单个托盘目标装载数量为 12。
- 后续空托盘用同一 carrier_tray_1 规范表示。
- 托盘槽位选择使用 first_empty_slot。

## open_questions

- 托盘目标装载数量是否固定为 12？
- 物料是否需要按类别放入指定槽位？
