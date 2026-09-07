# Scene 01 Normalized Case

## case_id

`scene_01_pallet_sorting_stop_point_conveyors`

## source_image

`docs/business/test/1.png`

## raw_description_summary

图 1 是一个托盘分拣场景：左侧托盘承载 12 个工件，中间由两段主传送带串联运输托盘，右侧有两台机械臂和上下两条出料传送带。托盘到位后，空闲机械臂从托盘上取料并放到出料传送带；出料传送带满载时暂停机械臂，恢复容量后继续。

## normalized_user_goal

这是一个托盘分拣场景。场景从左到右包括：一个装有 12 个工件的托盘、两段串联的主传送带、两台机械臂，以及右侧上下两条出料传送带。

运行开始后，托盘先进入第一段主传送带，并沿传送带停留点逐步向出口移动；当第一段出口与第二段入口可接收时，托盘转入第二段主传送带。第二段主传送带继续将托盘运输到机械臂可分拣位置。两段主传送带只负责托盘到位运输，不作为分拣出料缓存，因此第一阶段不考虑超载，只需要考虑停留点占用和下游是否可接收。

托盘到达分拣位置后，系统进入机械臂分拣阶段。两台机械臂共享托盘上的 12 个工件池；只有处于 idle 状态的机械臂才可以 claim 一个未处理工件。claim 成功后，机械臂执行 `pick_and_place`，将工件放到对应或被策略选中的出料传送带上。

右侧上下两条出料传送带需要考虑容量和停留点占用。每条出料传送带由若干停留点组成，工件进入后优先向最靠近出口的可用停留点移动；如果下游或出口被占用，后续工件依次停在前一个停留点。若某条出料传送带达到容量上限或无可用停留点，需要发出 `conveyor.blocked`；相关机械臂收到 `robot.pause_pick` 后，不再启动新的抓取任务。等出料传送带释放停留点并低于恢复阈值后，发出 `conveyor.capacity_available`，机械臂收到 `robot.resume_pick` 后恢复抓取。

仿真完成条件是：托盘上的 12 个工件全部完成分拣，所有传送带停留点为空，所有机械臂和传送带无 active action。

## device_inventory

| device_type | instance_id | spec_id | role |
|---|---|---|---|
| `conveyor` | `main_conveyor_1` | `conveyor_1` | 第一段主传送带，接收托盘并运输到第二段入口。 |
| `conveyor` | `main_conveyor_2` | `conveyor_1` | 第二段主传送带，接收托盘并运输到机械臂分拣位。 |
| `conveyor` | `upper_out_conveyor_1` | `conveyor_1` | 上方出料传送带，接收分拣后的工件并处理容量限制。 |
| `conveyor` | `lower_out_conveyor_1` | `conveyor_1` | 下方出料传送带，接收分拣后的工件并处理容量限制。 |
| `robot_arm` | `robot_1` | `robot_arm_1` | 分拣机械臂之一，从托盘取料并放料。 |
| `robot_arm` | `robot_2` | `robot_arm_1` | 分拣机械臂之一，从托盘取料并放料。 |
| `workpiece_carrier` | `pallet_1` | `carrier_tray_1` | 承载 12 个工件的托盘 / 物料载具。 |

## material_inventory

- `part_001` - `part_012`：初始位于 `pallet_1.slot_01` - `pallet_1.slot_12`。

## process_flow_summary

```text
pallet_1
  -> main_conveyor_1 stop points
  -> main_conveyor_2 stop points
  -> robot_1 / robot_2 shared claim
  -> upper_out_conveyor_1 or lower_out_conveyor_1 stop points
  -> output release / disappear
```

## key_runtime_constraints

- 主传送带容量按托盘处理，默认 `capacity = 1`，不启用分拣阶段 backpressure。
- 出料传送带默认 `capacity = 3`，`resume_threshold = 2`，需要处理 `blocked` 和 `capacity_available`。
- 所有传送带停留点由 `DeviceSpec.conveyor.type_specific_contract.stop_point_model` 和 `SceneDocument.instances[].param_overrides.stop_point_count` 共同决定。
- 机械臂只有 `idle` 且未被目标出料传送带 backpressure 暂停时才能 claim 新工件。
- 已启动的机械臂动作默认在安全边界完成后再进入等待状态，不强制中断半程动作。

## assumptions

- 传送带第一阶段采用线性插值停留点，不处理弯曲路径。
- 出料传送带末端释放后的工件可视为离开系统或进入未建模下游。
- 两台机械臂可以从同一个托盘共享工件池取料，具体目标传送带可由策略选择。
- 物料分类信息暂未细分时，默认用负载均衡策略选择上下出料传送带。

## open_questions

- 12 个工件是否存在明确分类，例如 A 类必须进入上方传送带、B 类必须进入下方传送带？
- 出料传送带末端是否连接真实下游设备，还是直接消失？
- 两台机械臂是否有固定负责区域，还是完全共享托盘工件池？
