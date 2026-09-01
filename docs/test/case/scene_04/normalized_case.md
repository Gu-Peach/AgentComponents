# Scene 04：传送带中段机械臂加工模拟 Normalized Case

## case_id

`scene_04_inline_conveyor_robot_processing`

## source_image

`docs/business/test/4.png`

## raw_description_summary

传送带起点直接生成或接收物料，物料移动到中间加工停留点后由机械臂执行固定位置操作，完成后继续沿传送带输出。

## normalized_user_goal

物料由传送带起点的上料台生成并进入主传送带，主传送带按停留点推进。工件到达中间加工停留点后，传送带暂停该工件的继续前进，空闲机械臂移动到固定加工位置执行一次模拟加工动作。加工完成后释放该停留点，物料继续沿传送带向出口移动并离开系统。若中间加工点被占用，后续物料停在上游停留点等待。

## device_inventory

| device_type | instance_id | spec_id | role |
|---|---|---|---|
| `material_source_station` | `source_station_1` | `material_source_station_1` | 传送带起点物料来源 |
| `conveyor` | `main_conveyor_1` | `conveyor_1` | 中段加工主传送带 |
| `robot_arm` | `robot_1` | `robot_arm_1` | 中段加工机械臂 |
| `robot_arm` | `robot_2` | `robot_arm_1` | 备用或第二加工机械臂 |

## material_inventory

- `part_001`
- `part_002`
- `part_003`
- `part_004`
- `part_005`
- `part_006`

## process_flow_summary

```text
source_station_1 -> main_conveyor_1 stop points -> processing_stop_point -> robot processing -> main_conveyor_1 exit
```

## key_runtime_constraints

- 加工停留点一次只处理一个物料。
- 物料未加工完成不能越过加工点。
- 后续物料必须在上游停留点等待。

## assumptions

- 机械臂加工动作暂用 pick_and_place 到同一工位的方式表达，后续可扩展 process_at_station 行为。
- robot_2 作为备用设备，baseline 优先 robot_1。

## open_questions

- 是否需要两个机械臂同时加工不同停留点？
- 加工时长是否固定？
