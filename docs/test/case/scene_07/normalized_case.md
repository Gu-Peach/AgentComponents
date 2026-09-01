# Scene 07：机床旁机械臂加工转运 Normalized Case

## case_id

`scene_07_machine_robot_process_transfer`

## source_image

`docs/business/test/7.png`

## raw_description_summary

输入传送带持续送入物料，机械臂从输入传送带取料到固定加工位模拟加工，完成后放到输出传送带。

## normalized_user_goal

输入传送带起点持续生成或接收物料，物料按停留点推进到靠近机械臂的取料点。机械臂空闲时从输入传送带出口取料，移动到机床或固定加工位，等待加工完成后再把物料放到输出传送带入口。输出传送带按停留点推进并在出口释放物料。输入传送带出口、加工位和输出传送带入口都需要互斥，防止物料穿透或重复搬运。

## device_inventory

| device_type | instance_id | spec_id | role |
|---|---|---|---|
| `material_source_station` | `source_station_1` | `material_source_station_1` | 输入物料来源 |
| `conveyor` | `input_conveyor_1` | `conveyor_1` | 输入传送带 |
| `robot_arm` | `robot_1` | `robot_arm_1` | 机床上下料机械臂 |
| `conveyor` | `output_conveyor_1` | `conveyor_1` | 输出传送带 |

## material_inventory

- `part_001`
- `part_002`
- `part_003`
- `part_004`
- `part_005`
- `part_006`

## process_flow_summary

```text
source_station_1 -> input_conveyor_1 stop points -> robot_1 -> machine_process_buffer -> robot_1 -> output_conveyor_1 stop points -> exit
```

## key_runtime_constraints

- 加工位一次只能处理一个物料。
- 输出传送带 blocked 时 robot_1 不能开始新的放料。
- 输入传送带出口占用时后续物料排队。

## assumptions

- 机床/加工位作为逻辑 process buffer 建模，不新增 DeviceSpec。
- 机械臂加工等待通过 state_transition_rules 中的 processing_timer 表达。

## open_questions

- 机床是否需要独立设备规范？
- 加工时长与加工成功/失败策略是否固定？
