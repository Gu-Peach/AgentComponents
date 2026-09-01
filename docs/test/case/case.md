# Prompt

````text
你需要基于下方 9 个测试场景描述，为当前 `SceneBehaviorGraph Agent` 设计一组可用于准确性校验的 benchmark case。

当前权威设计只采用新方案：

DeviceSpec + SceneDocument + 用户目标
  -> LangGraph Agent
  -> SceneBehaviorGraph
  -> Runtime 初始化 RuntimeSnapshot

不要使用旧方案中的 SimPlan，不要引用 else/ 下的旧设计文档，不要生成当前 SimulationSchema 中不存在的 schema 类型。

## 参考约束

生成内容必须严格遵守以下文档语义：

- `docs/business/SimulationSchema/README.md`
- `docs/business/SimulationSchema/device_data_structure.md`
- `docs/business/SimulationSchema/1.DeviceSpec/`
- `docs/business/SimulationSchema/2.SceneDocument/`
- `docs/business/SimulationSchema/3.RuntimeSnapshot/`
- `docs/business/SimulationSchema/4.SceneBehaviorGraph/`
- `docs/design/agent_design.md`

其中，Agent 的最终结构化产物只能是 `SceneBehaviorGraph`。`RuntimeSnapshot` 只作为运行时状态事实，不允许把运行期实时状态写成 Agent 的最终建模结果。

## 任务目标

请为每个场景完成以下工作：

1. 阅读原始场景描述，先整理一版更清晰、可执行、可校验的 `normalized_user_goal`。
2. 判断原始描述中是否存在歧义、缺失条件或和当前 schema 不兼容的要求，并给出 `assumptions` 与 `open_questions`。
3. 生成该场景对应的 `SceneBehaviorGraph` golden answer，用于后续评估 Agent 输出是否正确。
4. 为该场景生成一份面向人的解释文档，使用大白话说明行为图的运行链路、模块划分、事件、信号、策略和完成条件。
5. 为该场景生成一份测试断言，用于校验 Agent 输出是否覆盖关键业务行为。
6. 如果某个场景无法在当前 schema 约束下生成有效 `SceneBehaviorGraph`，不要硬编；输出失败报告，说明缺少哪些 DeviceSpec、SceneDocument 事实、信号口、行为能力或策略类型。

## 每个场景的输出结构

建议每个场景独立输出到一个目录：

```text
docs/test/case/scene_XX/
  README.md
  normalized_case.md
  scene_behavior_graph.golden.json
  graph_explanation.md
  test_assertions.json
  validation_report.md
```

### README.md

说明该 case 的测试目的、场景图片来源、用户目标摘要、涉及设备类型、主要调度难点和预期验证重点。

### normalized_case.md

必须包含：

- `case_id`
- `source_image`
- `raw_description_summary`
- `normalized_user_goal`
- `device_inventory`
- `material_inventory`
- `process_flow_summary`
- `key_runtime_constraints`
- `assumptions`
- `open_questions`

### scene_behavior_graph.golden.json

必须是完整 `SceneBehaviorGraph`，至少包含以下一级字段：

- `schema_id`
- `schema_type`
- `version`
- `name`
- `description`
- `source`
- `created_for`
- `references`
- `notes`
- `goal`
- `modules`
- `event_bus`
- `state_model`
- `behavior_rules`
- `state_transition_rules`
- `policies`
- `completion_conditions`
- `failure_observations`

`behavior_rules` 必须统一使用当前规则结构：

```text
trigger / guard / policy / action
```

不要使用旧口径 `when_event / when_state / if / then_*`。

### graph_explanation.md

用非代码语言解释该行为图，至少包括：

- 场景整体在做什么。
- 场景被拆成哪些工艺模块。
- 每个模块由哪些设备参与。
- 关键事件如何触发后续行为。
- 关键设备信号如何通过 `event_bus` 传递。
- Runtime 需要维护哪些重要状态。
- 哪些地方需要策略，例如共享工件池、队列等待、容量限制、资源锁、负载均衡、死锁检测。
- 什么条件下认为仿真完成。

### test_assertions.json

用于评估 Agent 输出，不要求和 golden JSON 字段逐字一致，但必须覆盖核心语义。建议包含：

- `must_have_modules`
- `must_have_events`
- `must_have_topics`
- `must_have_behavior_rules`
- `must_have_policies`
- `must_have_state_variables`
- `must_have_completion_conditions`
- `forbidden_schema_types`
- `forbidden_rule_forms`
- `minimum_validation_expectations`

### validation_report.md

说明 golden answer 是否满足当前 schema 约束，并列出：

- 已通过的约束。
- 需要后续 DeviceSpec 或 SceneDocument 补充的地方。
- 当前为了生成 case 作出的合理假设。
- 不能静态验证、必须交给 Runtime trace 验证的行为。

## 建模原则

- `DeviceSpec` 只表示设备本体能力，不保存场景连接关系。
- `SceneDocument` 表示场景事实，包括实例、位姿、物料和显式 `physical_edges / process_edges / signal_edges`。
- `SceneBehaviorGraph` 表示当前用户目标下的场景行为模型，是 Agent 的最终产物。
- `RuntimeSnapshot` 表示运行时实时状态，只能作为 Runtime 消费和更新的状态事实。
- `event_bus` 是 `SceneBehaviorGraph` 内部的事件/信号建模结果，不是独立 schema。
- `SignalBusRuntime` 是 Runtime 内部模块，只执行 `event_bus` 定义的事件校验、路由、topic 展开和投递。
- 高频设备运行、等待队列、资源锁、active actions 不由 Agent 高频决策，而由 Runtime Scheduler 根据 `SceneBehaviorGraph + RuntimeSnapshot` 执行。
- 所有传送带都必须建模停留点 / 占位点；Agent 不能把物料或托盘直接从 entry 移动到 exit，而应通过 `conveyor_stop_points`、`conveyor_occupancy`、`conveyor_queues` 和 `queue_wait` / `nearest_available_stop_point` / `capacity_threshold` / `downstream_release` 策略表达排队、等待、阻塞和释放。

## 质量要求

- 每个 golden answer 都应能被 `GraphValidator` 静态校验。
- 事件必须先注册在 `event_bus.events` 中，再被 routes、behavior_rules 或 state_transition_rules 引用。
- 设备信号必须尽量受对应 `DeviceSpec.signal_ports` 约束。
- 动态选择、资源抢占、容量限制、排队等待等逻辑必须落到 `policies` 或可校验的 `behavior_rules` 中。
- 不要把自然语言描述直接塞进 JSON 代替结构化字段。
- 不要为追求完整而发明当前规范没有定义的一级 schema。

## 当前第一阶段范围

当前先为每个场景生成一套 baseline case，每个场景只设计一种默认用户目标。后续再扩展同一场景下的多目标、多打断、多异常 case。
````

1. 第一张场景是托盘分拣场景。场景从左到右包括：一个装有 12 个工件的托盘、两段串联的主传送带、两台机械臂，以及右侧上下两条出料传送带。运行开始后，托盘先进入第一段主传送带，并沿传送带停留点逐步向出口移动；当第一段出口与第二段入口可接收时，托盘转入第二段主传送带。第二段主传送带继续将托盘运输到机械臂可分拣位置。两段主传送带只负责托盘到位运输，不作为分拣出料缓存，因此第一阶段不考虑超载，只考虑停留点占用和下游是否可接收。托盘到达分拣位置后，系统进入机械臂分拣阶段。两台机械臂共享托盘上的 12 个工件池；只有处于 idle 状态的机械臂才可以 claim 一个未处理工件。claim 成功后，机械臂执行 pick_and_place，将工件放到对应或被策略选中的出料传送带上。右侧上下两条出料传送带需要考虑容量和停留点占用：工件进入后优先向最靠近出口的可用停留点移动；如果下游或出口被占用，后续工件依次停在前一个停留点。若某条出料传送带达到容量上限或无可用停留点，需要发出 `conveyor.blocked`；相关机械臂收到 `robot.pause_pick` 后不再启动新的抓取任务。等出料传送带释放停留点并低于恢复阈值后，发出 `conveyor.capacity_available`，机械臂收到 `robot.resume_pick` 后恢复抓取。仿真完成条件是：托盘上的 12 个工件全部完成分拣，所有传送带停留点为空，所有机械臂和传送带无 active action。

2. 第二个场景是多机械臂远端优先托盘分拣线。场景从左到右包括托盘出料口、承载 12 个工件的托盘、长主传送带、三台机械臂，以及每台机械臂对应的一条出料传送带。出料口按节拍输出托盘，托盘进入主传送带后按停留点逐步前进。调度策略优先选择最远端空闲机械臂工位：如果 `robot_3` 空闲，托盘优先送到 `robot_3`；否则尝试 `robot_2`，再尝试 `robot_1`。当三台机械臂均忙时，主传送带保持当前停留点占用并停止继续放行，上游出料口暂停产生新托盘。机械臂从到位托盘中处理 12 个工件，并放入各自对应的出料传送带。每条出料传送带都按停留点容量处理 backpressure：满载或无停留点时发出 `conveyor.blocked`，容量恢复后发出 `conveyor.capacity_available`。空托盘沿主线继续到末端并离开系统。

3. 第三个场景是双机械臂接力运输机构。右侧物料上料台持续或按需生成工件，工件进入右侧传送带并按停留点移动到出口。当出口停留点有工件且第一台机械臂空闲时，`robot_1` 抓取工件并放到中间固定交接位。交接位被占用后，`robot_2` 在空闲且左侧传送带入口可接收时接走工件，并放入左侧传送带。左侧传送带继续按停留点运输到出口并释放。该场景默认启用排队等待；如果用户提出超载要求，则在同一 `conveyor_loads` 和 `capacity_threshold` 策略中启用容量限制。

4. 第四个场景是传送带中段机械臂加工模拟。物料由传送带起点的上料台生成并进入主传送带，主传送带按停留点推进。工件到达中间加工停留点后，传送带暂停该工件继续前进，空闲机械臂移动到固定加工位置执行一次模拟加工动作。加工完成后释放该停留点，物料继续沿传送带向出口移动并离开系统。若中间加工点被占用，后续物料停在上游停留点等待。

5. 第五个场景是圆桌双机械臂多出料分拣。圆桌中心作为物料呈现区域，人工上料过程第一阶段简化为 Runtime 在圆桌固定位置生成物料。两台机械臂监控圆桌上的待处理物料，谁空闲谁 claim 一个物料，并根据出料传送带容量选择空闲或负载较低的目标传送带。目标传送带入口停留点可用时，机械臂执行 `pick_and_place`；如果某条传送带 `blocked`，则该传送带不参与目标选择。所有出料传送带都必须按停留点推进和释放。

6. 第六个场景是仓储柜双升降台入库出库。左侧出料口按节拍生成物料，物料进入入口传送带并按停留点前进到第一升降台。第一升降台空闲且仓储柜存在空库位时，接收物料、移动到对应高度并将物料存入库位。第一升降台工作时，入口传送带出口物料等待，后续物料依次停在上游停留点。第二升降台根据出库策略从仓储柜取出物料，移动到末端传送带对接高度并释放物料。末端传送带按停留点运输到出口后物料离开系统。

7. 第七个场景是机床旁机械臂加工转运。输入传送带起点持续生成或接收物料，物料按停留点推进到靠近机械臂的取料点。机械臂空闲时从输入传送带出口取料，移动到机床或固定加工位，等待加工完成后再把物料放到输出传送带入口。输出传送带按停留点推进并在出口释放物料。输入传送带出口、加工位和输出传送带入口都需要互斥，防止物料穿透或重复搬运。

8. 第八个场景是物料与托盘同步到位装载。场景包含物料出料台、物料侧传送带、托盘、托盘侧传送带和一台机械臂。物料出料台持续输出工件，工件进入物料传送带并按停留点排队。空托盘进入托盘传送带并移动到装载位置。当物料传送带出口有工件且托盘到达装载位置时，机械臂抓取工件并放入托盘空槽。装载过程中，后续物料和托盘必须停在各自传送带上游停留点等待。托盘达到目标装载数量后，托盘传送带继续将该托盘运输到出口并离开系统，后续空托盘补位。

9. 第九个场景是旋转台定位与机械臂下料。场景包含物料来源、旋转台、机械臂和工作台。人工搬运步骤第一阶段不建模为独立 actor，而是简化为旋转台 `station_a` 生成或接收工件。旋转台检测 `station_a` 有工件后，执行 90 度离散旋转，把工件转到机械臂可达的 `station_b`。旋转到位后，空闲机械臂抓取工件并放到工作台固定位置。工件到达工作台后离开系统或标记为完成。旋转台工位占用、旋转资源、机械臂资源和工作台占用必须互斥。
