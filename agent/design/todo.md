# Agent Design TODO

> 日期：2026-09-08  
> 来源：`agent/design/design.md`  
> 目标：按阶段实现 Agent 侧“自动代理替代 VC 人工建模”的完整能力闭环。

---

## 0. 总体原则

- [ ] Agent 不直接高频控制 runtime；普通信号、FSM、资源锁和行为执行由 runtime 负责。
- [ ] Agent 所有写入都必须先生成 artifact / patch envelope，再经过校验、revision check 和审计。
- [ ] 拓扑、可达性、端口兼容、环路、资源容量等确定性问题由工具计算，LLM 只做语义解析、解释和候选修复。
- [ ] 每个模块同时交付工具契约、数据结构、日志事件、测试 fixture 和最小验收 case。
- [ ] 每一阶段完成后都能独立演示，不依赖后续阶段才能证明价值。

---

## Phase 0：设计基线与契约冻结

目标：统一 Agent 的职责边界、artifact 类型、工具分层和状态图，避免后续实现时把 Agent、Runtime、DB writer 混在一起。

### 交付物

- [x] 完成 `agent/design/design.md` 的 Agent 功能模块设计。
- [ ] 固化 `AgentState` 字段：scene、device specs、topology、intent、candidate artifacts、validation、runtime snapshot、final response。
- [ ] 固化 artifact 类型：`scene_patch`、`device_spec_patch`、`physical_edge_patch`、`process_patch`、`signal_patch`、`scene_behavior_graph_patch`、`parameter_binding_patch`、`diagnostic_report`、`question_set`、`scenario_experiment_plan`。
- [ ] 固化 `PatchEnvelope`：`base_scene_revision`、operations、reason、confidence、validation_before/after、approval_required、rollback_hint。
- [ ] 固化 agent event taxonomy：`agent.scene_loaded`、`agent.topology_built`、`agent.validation_failed`、`agent.patch_staged`、`agent.runtime_observation_diagnosed` 等。

### 工具

- [ ] `SchemaContractRegistry`：集中注册 Agent 输入/输出 schema。
- [ ] `ArtifactSchemaValidator`：校验所有候选 artifact 基础结构。
- [ ] `AgentEventEmitter`：统一记录 Agent 节点事件。

### 验收

- [ ] 任一候选 artifact 都能通过统一 schema 校验或返回结构化错误。
- [ ] 每次 Agent run 都能回放节点、artifact、校验结果和最终决策。

---

## Phase 1：数据访问与 Agent 运行骨架

目标：搭建 LangGraph 主链路和受控数据读写工具，让 Agent 能稳定读取场景、设备能力、拓扑、运行状态和历史 artifact。

### 交付物

- [ ] 实现 LangGraph 主图：`LoadContextNode -> LoadDeviceCapabilitiesNode -> BuildOrLoadTopologyNode -> ClassifyIntentNode -> ResolveSlotsNode -> RouteTaskNode -> ValidateArtifactNode -> RepairOrInterruptNode -> ExplainNode -> StageOrApplyNode -> EmitResultNode`。
- [ ] 实现 `AgentState` Pydantic / TypedDict 定义。
- [ ] 实现 run checkpoint、resume、cancel、repair_attempts 限制。
- [ ] 实现基础 SSE / event stream，用于前端展示 Agent 当前阶段。

### 工具

- [ ] `SceneReader(scene_id, revision?)`：读取 `SceneDocument`、active artifacts、revision。
- [ ] `DeviceSpecReader(spec_ids, version_policy?)`：读取设备规范和版本。
- [ ] `TopologyReader(scene_id, revision)`：读取缓存拓扑；revision 不匹配返回 null。
- [ ] `ArtifactReader(agent_run_id | scene_id)`：读取历史候选图、patch、诊断报告。
- [ ] `RuntimeSnapshotReader(run_id)`：只读 runtime snapshot。
- [ ] `EventLogReader(run_id, window, filters?)`：只读 runtime events / observations。
- [ ] `ArtifactWriter(agent_run_id, artifact)`：写候选 artifact，不改业务事实。

### 验收

- [ ] 给定 `scene_id + user_message`，Agent 能完整创建 run、读取 scene/spec/topology、输出只读诊断 artifact。
- [ ] 如果 scene revision 变化，旧 topology 和旧 patch 不会被误用。
- [ ] LLM 节点没有数据库直连权限，只能通过工具读写。

---

## Phase 2：确定性编译与 Guardian 校验基础

目标：先把“不能让 LLM 猜”的部分做成工具，包括接口编译、能力索引、拓扑构建、可达性和多层校验。

### 交付物

- [ ] `CapabilityIndex`：实例级行为、process port、physical interface、signal port、resource、capacity、默认参数索引。
- [ ] `CompiledInterfaceIndex`：把 `DeviceSpec.interface_bindings` 编译成实例级 physical/process/signal/behavior 绑定。
- [ ] `TopologyGraph` 基础版：显式 `physical_graph`、`process_graph`、`signal_graph`、`transport_graph`。
- [ ] `ValidationReport` 分级：blocking、warning、info。

### 工具

- [ ] `CapabilityIndexer(DeviceSpec[], SceneDocument)`：生成实例级能力索引。
- [ ] `InterfaceCompiler(SceneDocument, DeviceSpec[])`：编译三层接口绑定。
- [ ] `TopologyBuilder(SceneDocument, CapabilityIndex, options)`：从显式边生成拓扑图。
- [ ] `ReachabilityChecker(TopologyGraph, source, target, material_class?)`：查询物料/工艺/运输可达性。
- [ ] `SchemaValidator(artifact)`：JSON Schema / Pydantic 结构校验。
- [ ] `ReferenceValidator(artifact, SceneDocument, DeviceSpec[])`：引用完整性校验。
- [ ] `PortCompatibilityValidator(edges, CapabilityIndex)`：方向、类型、物料兼容校验。
- [ ] `BehaviorClosureValidator(SceneBehaviorGraph)`：trigger、guard、done、error、release 闭环校验。
- [ ] `RuntimePreflightValidator(SceneBehaviorGraph, RuntimeSnapshot?)`：初始事件、完成条件、启动条件校验。

### 可用开源依赖

- [ ] `pydantic` / `jsonschema`：结构校验。
- [ ] `networkx`：连通分量、路径、环路、拓扑排序。
- [ ] `scipy.spatial.KDTree` 或 `rtree`：后续隐式拓扑空间邻近搜索。

### 验收

- [ ] 无效 instance、port、behavior、event、state 引用都能被 blocking error 捕获。
- [ ] output->output、boolean->object signal 等错连能被捕获。
- [ ] 不存在任何 LLM 生成内容可以绕过 Guardian 写入最终图。

---

## Phase 3：SceneBehaviorGraph 生成 MVP

目标：实现用户自然语言到 `SceneBehaviorGraph` 的第一条可用闭环。

### 交付物

- [ ] `IntentParserNode`：输出 structured intent。
- [ ] `SlotResolverNode`：把“左侧传送带”“A2 格”“空闲机器人”解析为实例、端口、目标位置。
- [ ] `ProcessCompileSubgraph`：生成 process modules 和必要 `process_edges` patch。
- [ ] `SignalCompileSubgraph`：生成 signal plan、event bus routes、timeout/on_error 策略。
- [ ] `BehaviorGraphCompileSubgraph`：生成 `SceneBehaviorGraph` 草案。
- [ ] `ExplainNode`：输出 Agent 对场景调度的理解。
- [ ] `SceneBehaviorGraphWriter`：写候选图版本或最终图版本。

### 工具

- [ ] `IntentSchemaTool`：约束 LLM 结构化输出。
- [ ] `SlotResolver(SceneContext, TopologyGraph, user_slots)`：引用消解。
- [ ] `ProcessTemplateLibrary`：source、buffered transport、machine process、robot pick-place、sorting、backpressure 模板。
- [ ] `ProcessEdgePlanner`：生成或补齐 `process_edges`。
- [ ] `SignalPortResolver`：查找设备 signal ports 和方向。
- [ ] `SignalRoutePlanner`：生成 `signal_edges` 和 `event_bus.routes`。
- [ ] `EventBusBuilder`：注册事件、topics、subscriptions。
- [ ] `PolicyLibrary`：resource lock、queue wait、capacity threshold、workpiece claim、deadlock detection。
- [ ] `BehaviorGraphBuilder`：组装 events、states、rules、policies、completion、failure observations。

### 验收

- [ ] 输入“传送带末端有料时，让空闲机器人抓到 A2 格”，能生成合规 `SceneBehaviorGraph`。
- [ ] 图中所有 behavior 都来自 `DeviceSpec.transport_behaviors` 或明确的 `device_spec_patch` 候选。
- [ ] Runtime 不需要 LLM 即可消费该图推进基础行为。
- [ ] 自动修复最多 2 次，失败后输出结构化诊断而不是继续循环。

---

## Phase 4：拓扑自动补全与“只有位置”的场景建模

目标：覆盖用户只摆了设备位置、没画路由、没配信号时，Agent 主动补齐候选物理边、工艺边和信号边的能力。

### 交付物

- [ ] 隐式 physical edge 候选生成：距离、朝向、接口类型、物料类别、设备语义打分。
- [ ] physical edge -> process edge 派生规则。
- [ ] process edge -> signal handshake 派生规则。
- [ ] topology warning：孤立设备、悬空端口、方向冲突、类型不兼容、重复连接、环路。
- [ ] 低置信度候选的用户确认数据结构。

### 工具

- [ ] `WorldFrameResolver(instance.transform, physical_interface.local_frame)`：计算端口世界坐标和方向。
- [ ] `ImplicitEdgeCandidateGenerator`：生成候选边和 confidence。
- [ ] `EdgeConfidenceScorer`：融合几何、方向、类型、物料、语义分数。
- [ ] `TopologyWriter`：写入 topology artifact 或候选 edge patch。
- [ ] `PhysicalEdgePatchWriter`：生成 `physical_edges` patch。
- [ ] `ProcessPatchWriter`：生成 `process_edges` patch。
- [ ] `SignalPatchWriter`：生成 `signal_edges` patch。
- [ ] `ApprovalManager`：低置信度边进入确认。

### 验收

- [ ] 给定只有 instances + transform 的场景，能生成候选 topology 和缺失连接报告。
- [ ] 高置信度连接可暂存 patch，低置信度连接不会自动写入事实表。
- [ ] 如果目标不可达，Agent 输出“缺少哪条连接/哪个设备”的具体原因。

---

## Phase 5：文档参数抽取与参数绑定

目标：让 Agent 能从用户文档、说明书、验收文本中抽参数并绑定到数据库字段或行为图策略。

### 交付物

- [ ] 支持 Markdown / TXT / DOCX / XLSX / CSV / PDF 的参数抽取入口。
- [ ] `ParameterBindingPlan`：extracted params、target bindings、units_normalized、confidence、source trace、missing params。
- [ ] 参数绑定目标：`SceneDocument.instances[].param_overrides`、`runtime_config`、`SceneBehaviorGraph.policies`、`completion_conditions`。
- [ ] 支持把补全后的内容写回协作文档或需求文档。

### 工具

- [ ] `DocumentReader(document_id | storage_key | upload_id)`：读取文档元数据和内容。
- [ ] `DocumentParser(document_blob, mime_type)`：解析章节、表格、键值对、文本 span。
- [ ] `ParameterExtractor(parsed_document, extraction_schema)`：抽取节拍、速度、容量、故障率、验收指标。
- [ ] `UnitNormalizer(params)`：统一 SI 单位。
- [ ] `ParameterBinder(extracted_params, SceneContext, CapabilityIndex)`：绑定到具体字段路径。
- [ ] `ParameterPatchWriter`：生成参数 patch。
- [ ] `DocumentPatchWriter`：写回说明文档、验收文档或设计文档。

### 可用开源依赖

- [ ] `pypdf` / `pdfplumber`：PDF 文本和表格抽取。
- [ ] `python-docx`：Word 文档读写。
- [ ] `openpyxl`：Excel 参数表读写。
- [ ] `markdown-it-py` 或 `markdown`：Markdown 解析。
- [ ] OCR 可选：仅扫描件或图片文档需要。

### 验收

- [ ] “process time = 45s” 能绑定到具体机床或行为策略，而不是只作为自由文本保存。
- [ ] 所有关键参数都有 source trace、单位、confidence 和目标字段。
- [ ] 低置信度或多候选绑定不会自动写库，必须进入确认或 assumption。

---

## Phase 6：Runtime observation 诊断与修复闭环

目标：让 Agent 根据实时运行反馈解释报错，并生成可验证的修复 patch。

### 交付物

- [ ] observation 类型统一：deadlock、timeout、target_not_reached、resource_conflict、capacity_blocked、event_unconsumed、action_failed、completion_not_met、metric_violation、user_interrupt。
- [ ] `RuntimeDiagnosticReport`：symptom、root causes、evidence events、affected devices、suggested repairs、can_auto_repair。
- [ ] observation -> repair patch -> validation -> pause/replan/resume 流程。
- [ ] 运行时安全点策略：只有 runtime 暂停或到达 safe point 后才能应用修复。

### 工具

- [ ] `ObservationClassifier`：将 runtime observation 归类。
- [ ] `TraceAnalyzer(RuntimeSnapshot, EventLog, SceneBehaviorGraph)`：回溯事件、状态、资源锁、信号值。
- [ ] `RootCauseMapper`：把症状映射到缺边、缺路由、资源冲突、容量阻塞、行为失败。
- [ ] `RepairPlanner`：生成候选修复方案。
- [ ] `PatchStager`：暂存修复 patch。
- [ ] `PatchApplier`：通过 revision check 和事务写入事实表。
- [ ] `RuntimeControlTool`：pause、resume、cancel、replan request。

### 验收

- [ ] 缺失 `conveyor.part_ready -> robot.start_pick` 路由时，Agent 能从 event log 解释根因并生成 `signal_patch`。
- [ ] resource lock 长期不释放时，Agent 能定位占用者、等待者和相关规则。
- [ ] 未通过 validation 的修复 patch 不会被提交到 runtime。

---

## Phase 7：方案比较、业务验证与自动优化

目标：覆盖 VC 的核心工程价值：布局、产能、瓶颈、机器人单元、物流系统、虚拟调试和方案评审。

### 交付物

- [ ] scenario variant 生成：机器人数量、输送速度、缓存容量、工艺路线、投料频率。
- [ ] 仿真实验提交和批量运行。
- [ ] 指标采集：throughput、cycle time、WIP、waiting time、utilization、blocked time、deadlock count。
- [ ] `ScenarioComparisonReport`：方案、指标、瓶颈、tradeoff、推荐方案、模型置信度。
- [ ] 验收文档 assertions：吞吐量、节拍、WIP、利用率、超时率。

### 工具

- [ ] `ScenarioGenerator`：生成参数和结构变体。
- [ ] `SimulationSubmitter`：提交 simulation runs。
- [ ] `MetricsReader`：读取指标和事件统计。
- [ ] `BottleneckAnalyzer`：识别瓶颈设备、阻塞边和资源等待。
- [ ] `ScenarioReportWriter`：写报告 artifact。
- [ ] `RecommendationPlanner`：生成参数、布局、流程或策略修改建议。

### 可用开源依赖

- [ ] `pandas` / `numpy`：指标聚合。
- [ ] `scipy`：简单优化或参数扫描。
- [ ] `SimPy`：如果需要离线实验 runner。

### 验收

- [ ] 对同一场景能自动比较至少 2 个 variant。
- [ ] 报告能解释瓶颈来自设备节拍、容量、资源锁还是拓扑断链。
- [ ] 没有足够输入数据时，报告明确标注验证不能成立，不给虚假确定结论。

---

## Phase 8：模板库、记忆与复用

目标：把高频工业模式沉淀为模板，降低 LLM 每次从零生成的不稳定性。

### 交付物

- [ ] 模板 schema：适用设备类型、输入参数、输出片段、约束、校验器、版本。
- [ ] 模板类型：传送带 stop point、backpressure、多机器人 shared pool、pick-place、机床 process delay、货架格位、PLC-like 信号、deadlock observation。
- [ ] 模板检索：按设备类型、拓扑模式、用户意图、历史成功案例匹配。
- [ ] 模板版本化和回滚。

### 工具

- [ ] `PatternStoreReader`：读取可复用模式。
- [ ] `PatternStoreWriter`：写入人工确认或验证成功的模式。
- [ ] `EmbeddingSearchTool`：按语义检索模板。
- [ ] `TemplateInstantiator`：用当前 scene/spec 参数实例化模板。
- [ ] `TemplateValidator`：验证模板实例化后是否仍引用合法。

### 可用开源依赖

- [ ] `pgvector`：模板向量检索。
- [ ] sentence embedding 模型：可选，用于语义召回。

### 验收

- [ ] 同一类 pick-place / backpressure 场景不需要每次重新生成完整规则。
- [ ] 模板只能生成候选 artifact，不能绕过当前场景校验。

---

## Phase 9：外部联动与高保真扩展

目标：在内部事件行为总线稳定后，对接 PLC、OPC、机器人控制器或运动学/碰撞验证工具。

### 交付物

- [ ] OPC UA bridge 设计和最小映射。
- [ ] Siemens S7 bridge 设计和地址解析。
- [ ] Robot / ROS / MoveIt bridge 设计。
- [ ] HIL/SIL 联调模式。
- [ ] 高保真机器人路径、可达性和碰撞验证接口。

### 工具

- [ ] `ExternalSignalMapper`：内部 signal port 到外部变量地址映射。
- [ ] `OpcUaBridge`：OPC UA 读写、订阅、变量组同步。
- [ ] `S7Bridge`：S7 地址解析和批量读写。
- [ ] `RobotReachabilityChecker`：机器人可达性验证。
- [ ] `CollisionCheckAdapter`：碰撞检测适配。

### 验收

- [ ] 内部 `SignalBusRuntime` 不依赖外部 bridge 也能运行。
- [ ] 外部变量映射失败时，不破坏内部仿真状态。
- [ ] 高保真扩展只作为验证/增强层，不反向污染 P0-P6 的基础闭环。

---

## Phase 10：测试、基准与论文实验

目标：为实现和论文提供可复现的验证集，证明 Agent 确实替代了 VC 人工代理的关键工作。

### 交付物

- [ ] 场景 fixture：基础运输、机器人分拣、资源互斥、backpressure、缺信号、缺拓扑、文档填参、runtime deadlock。
- [ ] Golden `SceneBehaviorGraph` 和 semantic assertions。
- [ ] Agent run replay 测试。
- [ ] 工具单测：Reader、Builder、Validator、PatchApplier、TraceAnalyzer。
- [ ] 指标：生成成功率、校验通过率、自动修复成功率、用户确认次数、runtime observation 解决率、相比人工配置的步骤减少量。

### 工具

- [ ] `CaseRunner`：批量运行测试场景。
- [ ] `SceneBehaviorGraphAssertionRunner`：最终图结构和语义断言。
- [ ] `AgentReplayHarness`：重放 Agent run。
- [ ] `RuntimeObservationFixtureGenerator`：构造 deadlock/timeout/resource conflict 测试输入。

### 验收

- [ ] 每个 Phase 至少有 1 个端到端 case。
- [ ] 所有 blocking validation error 都有稳定 issue_code 和修复建议。
- [ ] 论文实验能复现“人工 VC 配置 vs Agent 自动代理”的任务时间、步骤数和错误率对比。

---

## 关键路径

```text
Phase 0 契约冻结
  -> Phase 1 数据访问与 Agent 骨架
  -> Phase 2 确定性编译 / Guardian
  -> Phase 3 SceneBehaviorGraph 生成 MVP
  -> Phase 4 拓扑补全 + Phase 5 文档填参
  -> Phase 6 Runtime 诊断修复
  -> Phase 7 方案比较优化
  -> Phase 8 模板记忆
  -> Phase 9 外部联动
  -> Phase 10 测试与论文实验
```

Phase 4 和 Phase 5 可以并行推进；Phase 7 依赖 Phase 6 的 observation 和 metrics；Phase 9 不应早于 Phase 3，否则外部联动会倒逼核心模型变形。
