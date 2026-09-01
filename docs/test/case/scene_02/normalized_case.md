# Scene 02：多机械臂远端优先托盘分拣线 Normalized Case

## case_id

`scene_02_multi_robot_farthest_idle_sorting_line`

## source_image

`docs/business/test/2.png`

## raw_description_summary

左侧出料口间隔输出承载 12 个工件的托盘，托盘沿长主传送带移动到三台机械臂工位；系统优先把新托盘送到最远端空闲机械臂，三台机械臂全忙时主线和出料口暂停。

## normalized_user_goal

场景从左到右包括托盘出料口、承载 12 个工件的托盘、长主传送带、三台机械臂，以及每台机械臂对应的一条出料传送带。出料口按节拍输出托盘，托盘进入主传送带后按停留点逐步前进。调度策略优先选择最远端空闲机械臂工位：如果 robot_3 空闲，托盘优先送到 robot_3；否则尝试 robot_2，再尝试 robot_1。当三台机械臂均忙时，主传送带保持当前停留点占用并停止继续放行，上游出料口暂停产生新托盘。机械臂从到位托盘中处理 12 个工件，并放入各自对应的出料传送带。每条出料传送带都按停留点容量处理 backpressure：满载或无停留点时发出 conveyor.blocked，容量恢复后发出 conveyor.capacity_available。空托盘沿主线继续到末端并离开系统。

## device_inventory

| device_type | instance_id | spec_id | role |
|---|---|---|---|
| `material_source_station` | `pallet_source_1` | `material_source_station_1` | 间隔生成装有 12 个工件的托盘 |
| `conveyor` | `main_conveyor_1` | `conveyor_1` | 长主传送带，沿三台机械臂工位分配托盘 |
| `robot_arm` | `robot_1` | `robot_arm_1` | 近端分拣机械臂 |
| `robot_arm` | `robot_2` | `robot_arm_1` | 中端分拣机械臂 |
| `robot_arm` | `robot_3` | `robot_arm_1` | 远端分拣机械臂 |
| `conveyor` | `robot_1_out_conveyor` | `conveyor_1` | robot_1 对应出料传送带 |
| `conveyor` | `robot_2_out_conveyor` | `conveyor_1` | robot_2 对应出料传送带 |
| `conveyor` | `robot_3_out_conveyor` | `conveyor_1` | robot_3 对应出料传送带 |

## material_inventory

- `pallet_01`
- `pallet_02`
- `pallet_03`

## process_flow_summary

```text
pallet_source_1 -> main_conveyor_1 stop points -> farthest idle robot station -> robot-specific output conveyor -> empty pallet exits main line
```

## key_runtime_constraints

- 远端优先分配托盘：robot_3 -> robot_2 -> robot_1。
- 三台机械臂全忙时，主传送带和出料口暂停。
- 所有传送带必须按停留点占用推进。
- 各机器人对应出料传送带需要 backpressure。

## assumptions

- 每个托盘默认包含 12 个同类工件。
- 空托盘到达主传送带末端后离开系统。
- 三台机械臂各自负责一个固定出料传送带。

## open_questions

- 是否需要持续生成无限托盘，还是只验证固定数量托盘？
- robot_3、robot_2、robot_1 的优先级是否始终固定？
