# Scene 03：双机械臂接力运输机构 Normalized Case

## case_id

`scene_03_two_robot_handoff_transport_line`

## source_image

`docs/business/test/3.png`

## raw_description_summary

右侧上料台产生物料，物料经右侧传送带到达终点后由第一台机械臂搬到固定交接位，第二台机械臂再从交接位搬到左侧传送带输出。

## normalized_user_goal

右侧物料上料台持续或按需生成工件，工件进入右侧传送带并按停留点移动到出口。当出口停留点有工件且第一台机械臂空闲时，robot_1 抓取工件并放到中间固定交接位。交接位被占用后，robot_2 在空闲且左侧传送带入口可接收时接走工件，并放入左侧传送带。左侧传送带继续按停留点运输到出口并释放。传送带默认只启用排队等待，也允许通过 capacity_threshold 扩展超载控制。

## device_inventory

| device_type | instance_id | spec_id | role |
|---|---|---|---|
| `material_source_station` | `source_station_1` | `material_source_station_1` | 右侧物料来源 |
| `conveyor` | `right_in_conveyor_1` | `conveyor_1` | 输入传送带 |
| `robot_arm` | `robot_1` | `robot_arm_1` | 从输入传送带搬到交接位 |
| `robot_arm` | `robot_2` | `robot_arm_1` | 从交接位搬到输出传送带 |
| `conveyor` | `left_out_conveyor_1` | `conveyor_1` | 输出传送带 |

## material_inventory

- `part_001`
- `part_002`
- `part_003`
- `part_004`
- `part_005`
- `part_006`

## process_flow_summary

```text
source_station_1 -> right_in_conveyor_1 stop points -> robot_1 -> handoff_buffer_1 -> robot_2 -> left_out_conveyor_1 stop points -> exit
```

## key_runtime_constraints

- 交接位一次只能放一个工件。
- 输入传送带出口占用时后续工件停在上游停留点。
- 输出传送带入口不可接收时 robot_2 等待。

## assumptions

- 固定交接位作为 SceneBehaviorGraph 状态资源建模，不新增独立 DeviceSpec。
- 当前 baseline 启用排队等待；若用户要求超载，则使用同一 capacity_threshold 策略。

## open_questions

- 固定交接位是否需要独立 3D 资产和 DeviceSpec？
- 物料生成是固定数量还是持续生成？
