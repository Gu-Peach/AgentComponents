# scene_01 Case Design Overview

## 场景摘要
- 场景名称：托盘分拣停留点传送线
- raw_description_summary：图 1 是一个托盘分拣场景：左侧托盘承载 12 个工件，中间由两段主传送带串联运输托盘，右侧有两台机械臂和上下两条出料传送带。托盘到位后，空闲机械臂从托盘上取料并放到出料传送带；出料传送带满载时暂停机械臂，恢复容量后继续。
- 主要设备：`main_conveyor_1`, `main_conveyor_2`, `upper_out_conveyor_1`, `lower_out_conveyor_1`, `robot_1`, `robot_2`, `pallet_1`
- 主要物料：part_001, part_002, part_003, part_004, part_005, part_006, part_007, part_008, part_009, part_010, part_011, part_012
- 显式连接：图片显示左侧托盘、水平主传送带、两台机械臂覆盖托盘分拣位，以及右侧上下两条出料传送带。
- 典型工艺目标：按图中空间布局完成物料流转，并用 `SceneBehaviorGraph` 表达事件、状态、策略与完成条件。

## Case 类型适用性判断

| Case 类型 | 是否适用 | 原因 | 本场景生成策略 |
|---|---|---|---|
| positive_basic | 是 | 所有场景都需要基础可运行图。 | case_01 和 case_02 覆盖基础流程与稳定节拍变体。 |
| parallel_collaboration | 是 | 图中存在多执行单元或可重叠工序，需要验证共享资源和动态选择。 | 生成并行协作 case。 |
| continuous_discrete_event | 是 | 包含停留点、加工/定位、阻塞释放或完成事件。 | case_04 覆盖连续状态到离散事件。 |
| negative_invalid | 是 | 必须包含。 | case_05 基于 case_01 引入不存在设备。 |
| semantic_interference | 是 | 必须包含。 | case_06 加入旧术语与口语化描述。 |

## 本场景最终 case 列表

| Case ID | Case 类型 | 用户目标摘要 | 基于哪个 case 修改 | 主要验证点 |
|---|---|---|---|---|
| scene_01_case_01 | positive_basic | 请按图里的布局跑一遍托盘分拣停留点传送线，让物料按场景描述完成基础流程，传送带要按停留点排队，不要把物料瞬移到终点。 | - | 最终图包含所有必填 section; 引用的设备和行为必须来自当前 DeviceSpec/SceneDocument |
| scene_01_case_02 | positive_basic | 在托盘分拣停留点传送线里优先保证节拍稳定：上游可以连续补料，但下游未释放时要等待；如果有多个目标设备，就按确定性优先级选择。 | - | 最终图包含所有必填 section; 引用的设备和行为必须来自当前 DeviceSpec/SceneDocument |
| scene_01_case_03 | parallel_collaboration | 我希望图中的可并行设备一起协作，谁空闲谁先处理，但共享工件、交接位或出口传送带不能被两个动作同时占用。 | - | 最终图包含所有必填 section; 引用的设备和行为必须来自当前 DeviceSpec/SceneDocument |
| scene_01_case_04 | continuous_discrete_event | 请重点验证连续输送到离散事件的转换：停留点占用、满载阻塞、释放恢复、加工或定位完成后再进入下一步。 | - | 最终图包含所有必填 section; 引用的设备和行为必须来自当前 DeviceSpec/SceneDocument |
| scene_01_case_05 | negative_invalid | 请强制让不存在的 robot_99 接管这个场景的关键动作，并且不要使用图中已有的正确设备。 | scene_01_case_01 | 最终图包含所有必填 section; 引用的设备和行为必须来自当前 DeviceSpec/SceneDocument |
| scene_01_case_06 | semantic_interference | 按这个场景生成图就行，但我以前叫它 SimPlan，也可能说成 SignalBusSchema；别被名字带偏。实际目标是图里的托盘分拣停留点传送线顺畅运行，谁空谁拿、别堵住、满了就等。 | scene_01_case_01 | 最终图包含所有必填 section; 引用的设备和行为必须来自当前 DeviceSpec/SceneDocument |
