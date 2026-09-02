# scene_05 Case Design Overview

## 场景摘要
- 场景名称：圆桌双机械臂多出料分拣
- raw_description_summary：圆桌固定位置生成物料，两台机械臂从圆桌取料并放到空闲出料传送带，多个出料传送带按停留点容量接收物料。
- 主要设备：`round_table_1`, `robot_1`, `robot_2`, `out_conveyor_1`, `out_conveyor_2`, `out_conveyor_3`, `out_conveyor_4`
- 主要物料：part_001, part_002, part_003, part_004, part_005, part_006, part_007, part_008
- 显式连接：图片显示中央圆桌、两台机械臂围绕圆桌，以及四条向外发散的绿色出料传送带。
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
| scene_05_case_01 | positive_basic | 请按图里的布局跑一遍圆桌双机械臂多出料分拣，让物料按场景描述完成基础流程，传送带要按停留点排队，不要把物料瞬移到终点。 | - | 最终图包含所有必填 section; 引用的设备和行为必须来自当前 DeviceSpec/SceneDocument |
| scene_05_case_02 | positive_basic | 在圆桌双机械臂多出料分拣里优先保证节拍稳定：上游可以连续补料，但下游未释放时要等待；如果有多个目标设备，就按确定性优先级选择。 | - | 最终图包含所有必填 section; 引用的设备和行为必须来自当前 DeviceSpec/SceneDocument |
| scene_05_case_03 | parallel_collaboration | 我希望图中的可并行设备一起协作，谁空闲谁先处理，但共享工件、交接位或出口传送带不能被两个动作同时占用。 | - | 最终图包含所有必填 section; 引用的设备和行为必须来自当前 DeviceSpec/SceneDocument |
| scene_05_case_04 | continuous_discrete_event | 请重点验证连续输送到离散事件的转换：停留点占用、满载阻塞、释放恢复、加工或定位完成后再进入下一步。 | - | 最终图包含所有必填 section; 引用的设备和行为必须来自当前 DeviceSpec/SceneDocument |
| scene_05_case_05 | negative_invalid | 请强制让不存在的 robot_99 接管这个场景的关键动作，并且不要使用图中已有的正确设备。 | scene_05_case_01 | 最终图包含所有必填 section; 引用的设备和行为必须来自当前 DeviceSpec/SceneDocument |
| scene_05_case_06 | semantic_interference | 按这个场景生成图就行，但我以前叫它 SimPlan，也可能说成 SignalBusSchema；别被名字带偏。实际目标是图里的圆桌双机械臂多出料分拣顺畅运行，谁空谁拿、别堵住、满了就等。 | scene_05_case_01 | 最终图包含所有必填 section; 引用的设备和行为必须来自当前 DeviceSpec/SceneDocument |
