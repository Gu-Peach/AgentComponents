# Agent 侧功能设计：从复刻 VC 到自动代理

> 版本：v0.1  
> 日期：2026-09-08  
> 范围：定义 Agent 为了替代 Visual Components 中依赖工程师手工配置的操作，应覆盖的功能模块、触发时机、验证层级和落地优先级。  
> 调研依据：`docs/research/business.md`、`docs/research/scene_runtime_execution_chain.md`、`docs/research/vc_runtime_signal_schema_research.md`、`docs/research/vc_topology_agent_research.md`。

---

## 0. 核心结论

当前项目已经跑通了 `SceneDocument -> TopologyGraph -> SignalBusRuntime -> DeviceRuntime -> 前端行为执行器` 的事件行为运行总线。进入 Agent 侧后，不能只把 Agent 理解为“根据用户需求生成运行时行为图”的 LLM 调度器。

更准确的定位是：**Agent 是把 VC 中人工完成的建模、连线、参数配置、脚本编排、校验排错、方案调参，转化为自动化编译与诊断流程的上层智能代理。**

因此 Agent 至少要覆盖五大能力域：

1. **场景理解与拓扑补全**：从 `SceneDocument`、设备位姿、端口和 `DeviceSpec` 中建立可运行拓扑，补齐用户没有显式连接的候选物理边、工艺边和信号边。
2. **工艺与行为图编译**：根据用户目标和场景拓扑生成 `SceneBehaviorGraph`，包括事件、状态、规则、策略、资源锁、完成条件和失败观测。
3. **参数与文档填充**：从用户说明、已有需求文档、设备规范、历史模板中抽取节拍、速度、容量、缓存、验收指标等参数，并把缺失项显式暴露为假设或追问。
4. **多层验证与守护**：在写入和运行前做 schema、引用、端口、拓扑可达性、资源互斥、容量、死锁、业务目标等校验，避免 LLM 幻觉式建模。
5. **运行反馈诊断与修复**：监听 runtime 升级出的 `simulation_observation`，解释报错原因，生成可审计修复 patch，而不是高频参与每个普通信号事件。

一句话：**Agent 不是替代 `SignalBusRuntime` 的实时控制器，而是替代 VC 专家用户的自动建模、自动校验、自动诊断和自动修复层。**

---

## 1. 设计边界

### 1.1 Agent 负责什么

- 理解用户自然语言目标，例如“让传送带出口物料由空闲机器人抓到 A2 货格”。
- 读取并摘要 `SceneDocument`、`DeviceSpec`、`TopologyGraph`、`RuntimeSnapshot`、运行日志和用户上传文档。
- 补全缺失建模信息，例如 `process_edges`、`signal_edges`、`SceneBehaviorGraph.event_bus`、状态变量和行为规则。
- 生成结构化 artifact，例如 `scene_patch`、`device_spec_patch`、`process_patch`、`signal_patch`、`scene_behavior_graph_patch`、`diagnostic_report`。
- 调用确定性工具做端口、拓扑、资源、容量、schema 和业务目标校验。
- 对 runtime observation 做根因分析和修复建议。
- 在低置信度、破坏性修改或业务含义不确定时触发用户确认。

### 1.2 Agent 不负责什么

- 不做每帧动画控制。
- 不替代 `SignalBusRuntime` 做普通信号投递。
- 不替代 `Device FSM Runtime` 做 busy/idle/block/error 的高频状态推进。
- 不直接操作 Three.js 模型位移。
- 不用 LLM 猜测拓扑图遍历、路径搜索、容量仲裁这类确定性问题。
- 不在未校验的情况下直接覆盖最终数据库状态。

### 1.3 核心分工

```text
Agent
  负责：理解、编译、补全、校验、解释、修复、重规划

Runtime
  负责：事件投递、FSM、资源锁、调度、行为执行、状态更新、指标采集

Frontend
  负责：场景编辑、行为动画播放、用户确认、日志与诊断展示
```

---

## 2. VC 人工操作替代矩阵

| VC 中的人工操作 | 当前痛点 | Agent 应替代的能力 | 主要输出 |
|---|---|---|---|
| 手动摆放设备并连接接口 | 用户常只给出位置，没有显式连接 | 拓扑理解、隐式连接候选、端口兼容性校验 | `physical_edges` 候选、topology warnings |
| 手动画 Process Modeling 流程 | 专家门槛高、流程和设备能力脱节 | 工艺流程自动编译 | `process_edges`、业务模块 DAG |
| 手工配信号线和 PLC-like I/O | 容易漏配、方向错、触发条件不清 | 信号路由与握手协议自动生成 | `signal_edges`、`event_bus.routes` |
| 手写 Python Script Behavior | 逻辑不可复用、难审计 | 行为图和策略函数生成 | `SceneBehaviorGraph` |
| 手工设置设备参数 | 参数散落在属性面板和文档里 | 参数抽取、默认值填充、缺失项追问 | `param_overrides`、assumptions |
| 手工检查布局和可达性 | 靠经验和目测，容易遗漏 | 静态拓扑/接口/可达性验证 | `diagnostic_report` |
| 手工排查运行报错 | 日志和场景状态割裂 | runtime observation 根因分析 | error explanation、repair patch |
| 手工比较方案和调参 | 重复劳动，缺少可复现记录 | 场景实验、参数敏感性、瓶颈解释 | scenario report、recommended patch |

---

## 3. Agent 功能模块总览

建议不要把下面每个模块都实现成一个自由运行的 ReAct Agent。更稳妥的方式是：**一个 LangGraph 状态机 + 多个确定性工具节点 + 少量 LLM 语义节点**。模块是能力边界，具体实现可以是 subgraph、tool node、model node 或 service。

| 模块 | 是否用 LLM | 核心输入 | 核心输出 | 作用 |
|---|---:|---|---|---|
| 1. 场景上下文构建 | 可选 | `SceneDocument`、revision、active artifacts | `SceneContext` | 建立 Agent 当前事实上下文 |
| 2. 设备能力索引 | 否/可选摘要 | `DeviceSpec` | `CapabilityIndex` | 索引接口、端口、行为、资源、容量 |
| 3. 拓扑理解与补全 | 图算法为主，LLM 解释 | 位姿、端口、显式边 | `TopologyGraph`、候选边、warnings | 解决“只给位置，没有路由”的问题 |
| 4. 文档与参数抽取 | 是 + 规则 | 用户文档、设备说明、验收文本 | 参数表、约束、验收指标、假设 | 从已有文档填参数和目标 |
| 5. 意图与场景解析 | 是 | 用户自然语言 + 拓扑摘要 | structured intent、slot resolutions | 判断用户要查询、连接、运行、诊断还是修改 |
| 6. 工艺流程编译 | 是 + 模板 | intent、topology、capability | `process_edges`、process modules | 替代手工 Process Modeling |
| 7. 信号与握手编译 | 是 + 规则 | process modules、signal ports、runtime contracts | `signal_edges`、event routes | 生成设备间等待、触发、互锁 |
| 8. 行为图编译 | 是 + 模板 | modules、events、states、policies | `SceneBehaviorGraph` | 生成 runtime 可执行行为模型 |
| 9. Guardian 校验 | 否为主，LLM 解释 | all candidate artifacts | validation report、repair hints | 防止幻觉边、错引用、死锁和不可达 |
| 10. 自动修复与 Patch | 是 + 工具 | validation/runtime observations | versioned patches | 修复缺边、缺参数、错路由、策略不闭环 |
| 11. Runtime 观察诊断 | 是 + 规则 | `RuntimeSnapshot`、event log、observation | root cause、fix plan | 根据实时反馈解释为什么跑不起来 |
| 12. 实验优化与方案比较 | 是 + 仿真工具 | 场景、指标、多个方案 | scenario report、推荐方案 | 对应产能、瓶颈、缓存、机器人数量验证 |
| 13. 记忆与模板库 | 可选 | 历史图、模式、用户偏好 | reusable patterns | 复用分拣、缓存、backpressure、资源锁模板 |
| 14. 协作与审计 | 否/可选解释 | agent events、patches、用户确认 | trace、explanation、approval record | 让建模过程可解释、可恢复、可复现 |

### 3.1 工具分层原则

Agent 不应直接拿数据库连接随意读写表，也不应让 LLM 自己拼 SQL 或 JSON Patch。正确做法是给 Agent 暴露一组**受控工具**，每个工具有固定输入输出 schema、权限边界、校验逻辑和审计记录。

工具分四类：

| 工具类型 | 是否自研 | 作用 | 典型工具 |
|---|---:|---|---|
| 数据读取工具 | 自研为主 | 从数据库/对象存储读取场景、设备、文档、运行日志 | `SceneReader`、`DeviceSpecReader`、`TopologyReader`、`RuntimeSnapshotReader`、`DocumentReader` |
| 编译/校验工具 | 自研 + 开源算法库 | 把事实编译成图、校验引用和可达性 | `InterfaceCompiler`、`TopologyBuilder`、`GraphValidator`、`ReachabilityChecker` |
| 内容解析工具 | 开源为主 + 自研绑定层 | 解析 PDF/Word/Markdown/表格，再映射到业务参数 | `DocumentParser`、`ParameterExtractor`、`UnitNormalizer`、`ParameterBinder` |
| 写入/编辑工具 | 自研为主 | 通过 patch 或事务写回数据库，不允许 LLM 直接改库 | `PatchStager`、`ScenePatchWriter`、`DeviceSpecPatchWriter`、`SceneBehaviorGraphWriter`、`DocumentPatchWriter` |

核心规则：

- **读库可以直接读，写库必须走 patch envelope**：读取 `SceneDocument`、`DeviceSpec`、`RuntimeSnapshot` 可以通过 repository 工具完成；写入必须先生成 artifact，再校验，再由 writer 工具事务提交。
- **文档编辑需要编辑类工具**：如果只是从文档抽参数，用 `DocumentReader + DocumentParser + ParameterExtractor`；如果要把补全后的内容写回需求文档、说明文档或设计文档，需要 `DocumentPatchWriter` 或文件/对象存储适配器。
- **数据库事实不要用“文档编辑工具”改**：`SceneDocument`、`DeviceSpec`、`TopologyGraph`、`SceneBehaviorGraph` 是结构化事实，应通过专门的 DB patch writer 改，不应把它们当普通文本替换。
- **开源工具负责通用能力，自研工具负责业务语义**：PDF/Word/Markdown/Excel 解析、图算法、JSON Schema 校验可以使用开源库；端口兼容、信号握手、行为图生成、revision check、审计写入必须自研。
- **所有工具都要可审计**：每次读了什么 revision、生成了什么 patch、校验前后差异、是否自动应用，都要写入 `agent_events` 或等价审计表。

### 3.2 数据库与文件写入边界

建议把 Agent 的写入分成三层，避免“直接编辑数据库内容”带来的不可回滚和不可解释问题。

| 写入层 | 目标 | 是否允许 Agent 直接写 | 推荐方式 |
|---|---|---:|---|
| 候选 artifact | `agent_artifacts` / 临时表 / 对象存储 | 是 | `ArtifactWriter` 写入候选结果和 validation report |
| 业务事实表 | scenes、device_specs、behavior_graphs、documents metadata | 间接允许 | `PatchStager -> Validator -> PatchApplier` 事务提交 |
| Runtime 状态 | Redis snapshot、event queue、active run | 受限 | 只允许 runtime control tool 修改，如 pause/resume/replan |

写库流程：

```text
LLM generates candidate artifact
  -> SchemaValidator
  -> ReferenceValidator
  -> Topology/Runtime preflight validator
  -> PatchStager writes pending patch
  -> approval policy decides auto apply or user confirm
  -> PatchApplier writes DB in transaction with revision check
  -> AuditLogger records before/after/reason/source
```

也就是说，Agent 可以“修改数据库中的内容”，但不应是任意 SQL 直改，而应是**通过带版本、校验、审计和回滚信息的 patch 工具修改结构化数据库事实**。

### 3.3 每个模块需要的工具

| 模块 | 必需工具 | 可用开源依赖 | 自研部分 | 是否读 DB | 是否写 DB |
|---|---|---|---|---:|---:|
| 场景上下文构建 | `SceneReader`、`ArtifactReader`、`RevisionResolver` | SQLAlchemy/SQLModel、Pydantic | 场景摘要、实例索引、revision 绑定 | 是 | 否 |
| 设备能力索引 | `DeviceSpecReader`、`CapabilityIndexer` | Pydantic、JSON Schema validator | 行为/端口/资源/容量索引规则 | 是 | 否 |
| 拓扑理解与补全 | `InterfaceCompiler`、`TopologyBuilder`、`ReachabilityChecker`、`TopologyWriter` | networkx、scipy KDTree / rtree | 端口世界坐标、隐式边打分、VC-like 接口兼容规则 | 是 | 可写候选 topology / edge patch |
| 文档与参数抽取 | `DocumentReader`、`DocumentParser`、`ParameterExtractor`、`ParameterBinder`、`DocumentPatchWriter` | pypdf/pdfplumber、python-docx、openpyxl、markdown-it/markdown、OCR 可选 | 参数语义映射、单位归一、目标字段绑定、来源追踪 | 是 | 可写参数 patch / 文档 patch |
| 意图与场景解析 | `IntentSchemaTool`、`SlotResolver`、`SceneQueryTool` | LLM structured output、Pydantic | intent taxonomy、设备/格位/方向引用消解 | 是 | 否 |
| 工艺流程编译 | `ProcessTemplateLibrary`、`ProcessEdgePlanner`、`ProcessPatchWriter` | networkx 可达路径 | 工业流程模块模板、process edge 生成规则 | 是 | 可写 `process_edges` patch |
| 信号与握手编译 | `SignalPortResolver`、`SignalRoutePlanner`、`EventBusBuilder`、`SignalPatchWriter` | JSON Schema validator | VC-like signal trigger、握手模板、timeout/on_error 策略 | 是 | 可写 `signal_edges` / event routes patch |
| SceneBehaviorGraph 编译 | `BehaviorGraphBuilder`、`PolicyLibrary`、`SceneBehaviorGraphWriter` | Pydantic、Jinja2 可选 | events/states/rules/policies/completion/failure 组装逻辑 | 是 | 是，写候选或最终行为图 |
| Guardian 校验 | `SchemaValidator`、`ReferenceValidator`、`PortCompatibilityValidator`、`BehaviorClosureValidator`、`RuntimePreflightValidator` | jsonschema、networkx、Pydantic | 业务级 blocking/warning 分级、修复建议生成 | 是 | 写 validation report |
| 自动修复与 Patch | `RepairPlanner`、`PatchStager`、`PatchApplier`、`RollbackPlanner` | jsonpatch、deepdiff 可选 | patch 策略、冲突处理、审批策略、审计 | 是 | 是，事务写事实表 |
| Runtime 观察诊断 | `RuntimeSnapshotReader`、`EventLogReader`、`ObservationClassifier`、`TraceAnalyzer` | pandas 可选用于日志分析 | 运行事件回溯、根因映射、修复候选 | 是 | 可写 diagnostic report / repair patch |
| 实验优化与方案比较 | `ScenarioGenerator`、`SimulationSubmitter`、`MetricsReader`、`ScenarioReportWriter` | SimPy、pandas、numpy、scipy 可选 | 工业指标、瓶颈解释、方案推荐逻辑 | 是 | 写 scenario runs / reports |
| 记忆与模板库 | `PatternStoreReader`、`PatternStoreWriter`、`EmbeddingSearchTool` | pgvector、sentence-transformers 可选 | 模式 schema、复用条件、版本化模板 | 是 | 是，写模板和经验 |
| 协作与审计 | `AgentEventEmitter`、`AuditLogger`、`ApprovalManager`、`TraceReader` | OpenTelemetry 可选 | agent event taxonomy、用户确认、回放数据结构 | 是 | 是，写 events/audit/approval |

### 3.4 建议工具清单

#### 数据读取工具

```text
SceneReader(scene_id, revision?)
  -> SceneDocument + active artifact refs

DeviceSpecReader(spec_ids, version_policy?)
  -> DeviceSpec[] + device capability summaries

TopologyReader(scene_id, revision)
  -> cached TopologyGraph or null

RuntimeSnapshotReader(run_id)
  -> RuntimeSnapshot

EventLogReader(run_id, window, filters?)
  -> recent runtime events / observations

DocumentReader(document_id | storage_key | upload_id)
  -> document metadata + raw/parsed content
```

#### 编译与校验工具

```text
InterfaceCompiler(SceneDocument, DeviceSpec[])
  -> compiled physical/process/signal interface index

TopologyBuilder(SceneDocument, CapabilityIndex, options)
  -> TopologyGraph + inferred candidates + warnings

ReachabilityChecker(TopologyGraph, source, target, material_class?)
  -> reachable / path / reason

SignalRoutePlanner(ProcessModelDraft, CapabilityIndex)
  -> signal edges + event routes

BehaviorGraphBuilder(intent, context, process_draft, signal_draft)
  -> SceneBehaviorGraph draft

GraphValidator(artifact, SceneDocument, DeviceSpec[], TopologyGraph?)
  -> ValidationReport
```

#### 文档解析与编辑工具

```text
DocumentParser(document_blob, mime_type)
  -> sections / tables / key_value_candidates / text spans

ParameterExtractor(parsed_document, extraction_schema)
  -> extracted params + confidence + source spans

ParameterBinder(extracted_params, SceneContext, CapabilityIndex)
  -> ParameterBindingPlan

DocumentPatchWriter(document_id, patch_ops, base_version)
  -> updated document version
```

文档类工具建议使用开源解析库作为底层能力，但**字段绑定和写回策略必须自研**：开源库能读写 Word/PDF/Markdown/Excel，却不知道“45s process time 应该绑定到哪台 machine 的 `param_overrides.process_time_s`”。这个语义绑定必须由 Agent 工具层完成。

#### 写入与审计工具

```text
ArtifactWriter(agent_run_id, artifact)
  -> artifact_id

PatchStager(agent_run_id, patch_envelope)
  -> pending_patch_id

PatchApplier(pending_patch_id, expected_base_revision)
  -> new_revision / conflict

SceneBehaviorGraphWriter(scene_id, graph, base_scene_revision)
  -> graph_id / graph_revision

AuditLogger(event)
  -> audit_event_id
```

这些写入工具应封装数据库事务：

- 读取当前 revision。
- 比对 `base_scene_revision`。
- 应用 JSON Patch 或领域命令。
- 重新运行必要 validator。
- 写入新 revision 和审计事件。
- 返回可给前端展示的 diff 摘要。

### 3.5 自研与开源取舍

| 能力 | 建议 | 原因 |
|---|---|---|
| PDF/Word/Markdown/Excel 读取 | 优先开源 | 文件解析是通用能力，没必要自研。 |
| 文档内容写回 | 开源库 + 自研 patch adapter | 开源库负责格式写入，自研层负责版本、权限、审计和语义定位。 |
| JSON Schema / Pydantic 校验 | 开源 + 自研规则 | 结构校验通用，业务规则必须自研。 |
| 图算法、路径、连通分量 | 开源 networkx + 自研封装 | 算法通用，但端口语义和置信度评分是业务特有。 |
| 空间邻近搜索 | scipy KDTree / rtree 可选 | 通用算法成熟，自研只做接口世界坐标和过滤规则。 |
| SceneDocument / DeviceSpec 写入 | 必须自研 | 涉及 revision、权限、领域约束和审计，不能交给通用工具任意改。 |
| Signal / handshake 编译 | 必须自研 | 这是平台核心壁垒，直接决定 runtime 能否正确执行。 |
| Runtime observation 诊断 | 自研为主 | 需要理解本平台事件语义、状态模型、资源锁和行为图。 |
| Scenario 对比分析 | pandas/numpy + 自研指标解释 | 指标计算可用开源，工程解释和建议策略要自研。 |

---

## 4. 模块详细设计

### 4.1 场景上下文构建模块

**目标**：把当前场景事实整理成 Agent 可消费的上下文，而不是让 LLM 直接读完整 JSON。

输入：

- `scene_id`
- `scene_revision`
- `SceneDocument.instances[]`
- `SceneDocument.materials[]`
- `SceneDocument.physical_edges[]`
- `SceneDocument.process_edges[]`
- `SceneDocument.signal_edges[]`
- 当前 `TopologyGraph` 引用
- 当前 `SceneBehaviorGraph` 引用
- 可选 `RuntimeSnapshot`

输出：

```text
SceneContext
  - instance_index
  - material_index
  - explicit_physical_edges
  - explicit_process_edges
  - explicit_signal_edges
  - active_artifact_refs
  - scene_summary_for_llm
  - blocking_missing_facts
```

设计要求：

- 保留 `scene_revision`，所有后续 patch 都必须绑定该 revision。
- 对 LLM 只暴露摘要和索引，不把大 JSON 原样塞入上下文。
- 若 `SceneDocument` 只有位置信息但没有连接，应标记 `process_edges_missing`、`signal_edges_missing`，进入拓扑补全流程。

### 4.2 设备能力索引模块

**目标**：把 `DeviceSpec` 中设备“能做什么”编译成可查询索引。

输入：

- 场景中所有 `spec_id`
- `DeviceSpec.physical_interfaces[]`
- `DeviceSpec.process_ports[]`
- `DeviceSpec.signal_ports[]`
- `DeviceSpec.interface_bindings[]`
- `DeviceSpec.transport_behaviors[]`
- `DeviceSpec.runtime_contract`
- `DeviceSpec.type_specific_contract`

输出：

```text
CapabilityIndex
  - behavior_index: instance_id -> behavior_id -> contract
  - process_port_index: instance_id.port_id -> direction/material_classes
  - physical_interface_index: instance_id.interface_id -> world frame/compatibility
  - signal_port_index: instance_id.port_id -> direction/value_type/trigger
  - binding_index: physical/process/signal/behavior binding
  - resource_index: resource type/capacity/mutex group
  - default_param_index: default timing/speed/capacity/thresholds
```

设计要求：

- `DeviceSpec` 是能力边界，Agent 不能凭空发明设备不存在的行为。
- 如果自然语言需要一个不存在的信号口或行为，Agent 应输出 `device_spec_patch` 候选，而不是直接在 `SceneBehaviorGraph` 里引用虚构端口。
- 对传送带、机器人、机床、升降台、货架等核心设备建立类型特化摘要，降低 LLM 推理难度。

### 4.3 拓扑理解与补全模块

**目标**：解决 VC 没有自动全局拓扑理解的问题，也是替代人工连线的关键模块。

该模块分两层：

1. **确定性 Topology Builder**：纯代码计算端口世界坐标、显式边、候选隐式边、连通分量、可达路径、悬空端口、环路。
2. **Topology Explanation Agent**：LLM 只负责把图算法结果解释成用户和下游 Agent 能读懂的摘要，不负责猜边。

输入：

- `SceneDocument.instances[].transform`
- `DeviceSpec.physical_interfaces[]`
- `DeviceSpec.process_ports[]`
- `DeviceSpec.signal_ports[]`
- 显式 `physical_edges/process_edges/signal_edges`
- 物料类型、端口方向、接口兼容性字段

输出：

```text
TopologyGraph
  - physical_graph
  - process_graph
  - signal_graph
  - transport_graph
  - inferred_edge_candidates
  - reachability_index
  - topology_summary
  - warnings
```

隐式补全规则：

- 空间距离足够近。
- 输出端口对输入端口，或双向端口兼容。
- 端口朝向相对合理。
- 物料类型、接口类型、产品族兼容。
- 设备语义合理，例如 conveyor.exit 更可能接 conveyor.entry / machine.input / robot.pick_area，而不是接另一个 output。
- 高置信度候选可自动生成 patch，低置信度候选只进入建议列表或用户确认。

关键场景：

```text
输入 SceneDocument：
  只有设备 instance、位置、朝向，没有 process_edges 和 signal_edges。

Agent 应执行：
  1. 由 DeviceSpec 计算所有端口世界坐标。
  2. 推断 conveyor.exit -> machine.entry 这类物理候选边。
  3. 基于物理候选边生成 process_edges 候选。
  4. 基于设备 runtime_contract 生成 signal_edges / event routes 候选。
  5. 输出完整补全 patch 和低置信度连接说明。
```

### 4.4 文档与参数抽取模块

**目标**：解决“已有文档里有参数，用户不想在每台设备属性面板里手填”的问题。

输入来源：

- 用户自然语言。
- 设备说明书。
- 产线验收文档。
- 工艺流程说明。
- 表格、Markdown、PDF、图片 OCR 后的结构化文本。
- 历史场景模板。

需要抽取的内容：

- 设备参数：速度、加速度、节拍、容量、缓存数、停留点数量、工位数量、故障率、换型时间。
- 运行参数：仿真时长、投料频率、产品 mix、优先级规则、批量大小。
- 工艺约束：先后顺序、并行关系、互锁条件、质量分流规则、异常处理规则。
- 验收指标：吞吐量、节拍、WIP、利用率、等待时间、瓶颈位置、目标达成条件。
- 边界条件：哪些物理过程不模拟、哪些动作只抽象为延时、哪些路径需要机器人可达性验证。

输出：

```text
ParameterBindingPlan
  - extracted_params
  - target_bindings
  - units_normalized
  - confidence
  - source_citations
  - missing_required_params
  - assumptions
```

设计要求：

- 参数必须绑定到具体目标：`DeviceSpec` 默认值、`SceneDocument.instances[].param_overrides`、`runtime_config` 或 `SceneBehaviorGraph.policies`。
- 单位必须规范化，后端 canonical schema 建议统一 SI 单位。
- 不能把无法定位来源的参数静默写入；低置信度参数要成为 assumption 或 question。
- 文档抽取结果要可追溯，便于论文实验和工程审计。

### 4.5 意图与操作场景解析模块

**目标**：让用户可以描述操作场景，而不是直接写流程图或信号图。

典型输入：

- “这条线跑 30 分钟，看看瓶颈在哪里。”
- “传送带末端有料时，让空闲机器人抓到 A2 格。”
- “下游满了就让上游等，不要继续堆料。”
- “用两台机器人并行分拣，谁空闲谁先抓。”
- “刚才仿真为什么卡住了？”
- “按这份验收文档把参数填进去。”

输出 intent：

```json
{
  "intent_type": "simulation_plan | process_config | topology_diagnosis | runtime_diagnosis | parameter_fill | device_edit | scene_query | scenario_compare",
  "goal": "用户目标",
  "target_instances": [],
  "source_slots": {},
  "constraints": [],
  "success_criteria": [],
  "requires_user_confirmation": false
}
```

设计要求：

- 引用消解必须基于 `TopologyGraph` 和 `SceneContext`，例如“左侧传送带”“A2 格”“空闲机器人”。
- 如果用户目标和当前场景事实矛盾，应进入诊断或追问，而不是强行生成行为图。
- 对“查询/诊断/解释”类请求，不应写入场景；对“配置/修复/运行”类请求，应输出候选 artifact 并校验。

### 4.6 工艺流程编译模块

**目标**：替代 VC 的手工 Process Modeling，把用户目标和场景拓扑编译成业务模块和工艺边。

输入：

- structured intent
- `TopologyGraph.process_graph / physical_graph / transport_graph`
- `CapabilityIndex`
- 产品类型、物料来源、目标位置

输出：

```text
ProcessModelDraft
  - process_modules
  - process_edges_patch
  - module_dependencies
  - material_flow_plan
  - assumptions
```

常见模块模式：

- `source_feed`：物料源投料。
- `buffered_transport`：带停留点/缓存的传送。
- `machine_process`：占用资源 + 延时 + 状态变化。
- `robot_pick_place`：机器人抓取/放置，含资源锁和可达性约束。
- `storage_putaway/retrieval`：货格入库/出库。
- `sorting`：按产品类型或质量分流。
- `parallel_collaboration`：多机器人或多设备共享任务池。
- `backpressure_control`：下游满载导致上游等待。

设计要求：

- `process_edges` 只表达物料/工艺流，不混入 signal edge。
- 模块必须能映射到设备已有行为能力。
- 若用户目标跨越不可达拓扑，输出诊断报告或候选连接 patch。

### 4.7 信号与握手编译模块

**目标**：把“设备之间互相等待、触发、互锁和释放”的控制关系补齐。

输入：

- `ProcessModelDraft`
- `CapabilityIndex.signal_port_index`
- `DeviceSpec.runtime_contract`
- `TopologyGraph.signal_graph`
- 业务策略，例如 backpressure、resource lock、queue wait

输出：

```text
SignalPlanDraft
  - signal_edges_patch
  - event_bus.events
  - event_bus.routes
  - event_bus.topics
  - event_bus.subscriptions
  - timeout_policy
  - transform_policy
```

典型握手模式：

```text
upstream.part_ready
  -> downstream.capacity_available && target.idle
  -> target.start_behavior
  -> target.behavior_running
  -> target.behavior_done
  -> upstream.release_material
```

必须覆盖的信号语义：

- `part_ready / material_arrived`
- `capacity_available / full / blocked`
- `start / pause / resume / reset`
- `busy / idle / ready`
- `behavior_done / behavior_error`
- `resource_acquired / resource_released`
- `timeout / deadlock / target_not_reached`

设计要求：

- 信号端口必须来自 `DeviceSpec.signal_ports` 或经过 `device_spec_patch` 明确新增。
- 对每条 signal edge 标注 trigger：`on_rising_edge`、`on_change`、`level` 等。
- 对命令类信号和状态类信号做区分，避免把 `latest_value` 当成一次事件。
- 所有 timeout 都要落到 `failure_observations` 或 retry policy，不能静默失败。

### 4.8 SceneBehaviorGraph 编译模块

**目标**：生成当前系统最核心的 Agent 产物：可解释、可校验、可运行的 `SceneBehaviorGraph`。

输入：

- structured intent
- `SceneContext`
- `CapabilityIndex`
- `TopologyGraph`
- `ProcessModelDraft`
- `SignalPlanDraft`
- 策略模板库

输出字段：

```text
SceneBehaviorGraph
  - goal
  - modules
  - event_bus
  - state_model
  - behavior_rules
  - state_transition_rules
  - policies
  - completion_conditions
  - failure_observations
  - assumptions
  - source_trace
```

设计要求：

- Runtime 高频执行不依赖 LLM，必须能只读 `SceneBehaviorGraph + RuntimeSnapshot` 推进。
- 图中所有引用必须能回到 `SceneDocument` 或 `DeviceSpec`。
- 对连续动作要离散事件化，例如“传送带持续运行”应拆成 stop point、occupancy、queue、capacity、blocked/release 事件。
- 对机器人/升降台/共享资源必须生成资源锁和释放条件。
- 对并行协作必须生成 claim 策略，避免两台设备抢同一物料。

### 4.9 Guardian 校验模块

**目标**：把 Agent 从“会写 JSON 的 LLM”变成可靠的建模系统。

校验分层：

| 层级 | 名称 | 校验内容 | 阻塞条件示例 |
|---|---|---|---|
| L0 | Schema / JSON 结构校验 | schema 类型、必填字段、枚举、payload 类型 | `SceneBehaviorGraph` 缺少 `event_bus` |
| L1 | 引用完整性校验 | instance、material、behavior、port、state、event 引用存在 | 引用了不存在的 `robot_3` |
| L2 | 端口与接口校验 | 方向、物料类型、接口兼容、信号 value type | output 连 output，boolean 发给 object port |
| L3 | 拓扑可达性校验 | process path、transport path、目标位置可达 | A2 货格与升降台无有效路径 |
| L4 | 行为闭环校验 | trigger、guard、effect、done/error、release 是否闭环 | 行为开始后没有 done 事件 |
| L5 | 资源与容量校验 | mutex、claim、buffer、backpressure、deadlock 风险 | 两机器人可同时 claim 同一工件 |
| L6 | Runtime preflight | 初始状态、事件队列、完成条件是否可启动 | 没有任何事件能触发第一步 |
| L7 | 业务目标校验 | 吞吐量、节拍、利用率、验收断言 | 目标要求 400 件/h，但模型未注册指标 |

输出：

```text
ValidationReport
  - severity: blocking | warning | info
  - issue_code
  - message_for_user
  - affected_artifact_path
  - suggested_fix
  - auto_fixable
```

设计要求：

- blocking error 禁止写入最终图或提交仿真。
- 自动修复最多循环 2 次，仍失败则给出诊断和候选问题，不进入无界 self-reflection。
- LLM 可以解释错误，但不能跳过确定性校验。

### 4.10 自动修复与 Patch 模块

**目标**：让 Agent 不只报错，还能生成安全、可审计的修复动作。

常见修复类型：

- 补 `process_edges`。
- 补 `signal_edges`。
- 补 `SceneBehaviorGraph.event_bus.routes`。
- 补 state variable、completion condition、failure observation。
- 修正端口方向或 edge trigger。
- 根据文档填入 `param_overrides`。
- 对缺失设备行为生成 `device_spec_patch` 候选。
- 对低置信度拓扑候选生成 `question_set` 或“待确认连接”。

Patch 约束：

```text
PatchEnvelope
  - patch_id
  - artifact_type
  - base_scene_revision
  - operations
  - reason
  - confidence
  - validation_before
  - validation_after
  - approval_required
```

设计要求：

- 所有 patch 都绑定 `base_scene_revision`，防止场景变更后误写。
- 高置信度、非破坏性、可回滚 patch 可以自动暂存；破坏性或低置信度 patch 必须用户确认。
- patch 应尽量小，不直接覆盖完整 `SceneDocument`。

### 4.11 Runtime 观察诊断模块

**目标**：基于实时运行反馈，让 Agent 能回答“为什么跑不起来、哪里堵了、该怎么修”。

触发源不是普通 `signal_event`，而是 runtime 升级出的 observation：

- `deadlock`
- `timeout`
- `target_not_reached`
- `resource_conflict`
- `capacity_blocked`
- `event_unconsumed`
- `action_failed`
- `completion_not_met`
- `metric_violation`
- `user_interrupt`

输入：

- `RuntimeSnapshot`
- recent event log
- active actions
- resource locks
- material locations
- signal latest values
- `SceneBehaviorGraph`
- validation report

输出：

```text
RuntimeDiagnosticReport
  - symptom
  - probable_root_causes
  - evidence_events
  - affected_devices
  - suggested_repairs
  - can_auto_repair
  - next_user_question
```

示例：

```text
现象：robot_1 一直等待 start_pick。
证据：conveyor_1.part_ready=True 已发出，但没有路由到 robot_1.start_pick。
根因：SceneDocument.signal_edges 缺少 conveyor_1.part_ready -> robot_1.start_pick。
修复：新增 signal_edge，并补充 robot_1 pick_and_place 的 completion route。
```

设计要求：

- 诊断必须引用运行日志和状态快照，不能只给泛泛建议。
- Agent 可以提出重规划，但 runtime 仍应在安全点暂停后再应用 patch。
- 对“运行时观察 -> 修复 -> 继续运行”保留完整审计链。

### 4.12 实验优化与方案比较模块

**目标**：覆盖 `business.md` 提到的 VC 有意义场景：布局、产能、方案比较、机器人单元、物流、虚拟调试、展示培训。

能力：

- 自动生成多个 scenario variant，例如机器人数量、输送速度、缓存容量、工艺路线、投料频率。
- 运行或提交仿真实验，收集吞吐、WIP、等待时间、设备利用率、瓶颈、阻塞时间。
- 对比方案并解释差异。
- 根据瓶颈生成候选修复，例如增加缓存、改变优先级、拆分共享资源、调整节拍。
- 把用户验收指标转成 `completion_conditions` 和 `metric assertions`。

输出：

```text
ScenarioComparisonReport
  - variants
  - metrics
  - bottlenecks
  - tradeoffs
  - recommended_variant
  - required_model_confidence
```

边界：

- 第一阶段不做切削、焊接质量、热变形等微观物理预测。
- 若用户要求这类高保真物理判断，应输出能力边界说明，并建议外部 CAE/CAM/工艺模型集成。

### 4.13 记忆与模板库模块

**目标**：避免每次从零生成，把高频工业模式沉淀成可复用模板。

模板类型：

- 传送带 stop point / occupancy / queue 模板。
- 下游满载 backpressure 模板。
- 多机器人 shared workpiece pool 模板。
- 机器人 pick-place 握手模板。
- 机床 process delay + door/fixture interlock 模板。
- 货架 A/B/C 格位入库出库模板。
- PLC-like `FROM_PLC_* / TO_PLC_*` 信号命名模板。
- deadlock / timeout / target_not_reached observation 模板。

设计要求：

- 长期记忆只能提供候选模式，不能绕过当前场景事实校验。
- 模板应版本化，方便论文实验对比“无模板 vs 有模板”的 Agent 稳定性。

### 4.14 协作、解释与审计模块

**目标**：让用户能看懂 Agent 做了什么，也让论文和工程排错可复现。

需要输出的事件：

- `agent.scene_loaded`
- `agent.device_specs_loaded`
- `agent.topology_built`
- `agent.intent_parsed`
- `agent.parameters_extracted`
- `agent.process_draft_created`
- `agent.signal_plan_created`
- `agent.behavior_graph_created`
- `agent.validation_failed`
- `agent.validation_repaired`
- `agent.waiting_for_user_review`
- `agent.patch_staged`
- `agent.finalized`
- `agent.runtime_observation_diagnosed`

解释内容：

- 我识别到哪些设备、物料和路径。
- 我补全了哪些边，哪些是显式边，哪些是推断候选。
- 我生成了哪些事件、状态和行为规则。
- 我启用了哪些策略，例如 resource lock、queue wait、backpressure。
- 我发现了哪些风险，哪些已自动修复，哪些需要用户确认。

---

## 5. 推荐工作流

### 5.1 用户请求驱动工作流

```text
用户自然语言
  -> LoadSceneContext
  -> LoadDeviceCapabilities
  -> BuildOrLoadTopology
  -> ExtractIntentAndSlots
  -> RouteTask
  -> GenerateCandidateArtifact
  -> Validate
  -> RepairOrAsk
  -> ExplainAndStage
  -> ApplyOrSubmitRuntime
```

### 5.2 场景变更驱动工作流

```text
device_added / device_moved / port_connected / params_updated
  -> Rebuild affected interface world frames
  -> Incremental Topology Builder
  -> Consistency Checker
  -> Update topology cache
  -> Emit warnings / suggested connections
```

说明：场景变更不一定调用 LLM。只有需要自然语言解释、低置信度决策或复杂修复时才进入 LLM 节点。

### 5.3 文档填参工作流

```text
用户上传或引用文档
  -> Document Extractor
  -> Parameter Normalizer
  -> Binding Resolver
  -> Missing Parameter Detector
  -> Generate param patch / question_set
  -> Validate units/ranges/references
  -> Stage patch
```

### 5.4 Runtime observation 工作流

```text
Runtime emits simulation_observation
  -> Load RuntimeSnapshot + recent event log
  -> Classify observation
  -> Trace root cause against SceneBehaviorGraph/TopologyGraph
  -> Generate diagnostic report
  -> Generate repair candidates if possible
  -> Validate repair patch
  -> Pause/replan/resume or ask user
```

---

## 6. “只有位置信息，没有信号路由”的补全策略

这是 Agent 侧必须优先覆盖的核心场景。

### 6.1 输入状态

```text
SceneDocument.instances[] 有：
  - instance_id
  - spec_id
  - transform / position / rotation
  - param_overrides 可选

SceneDocument 缺少或不完整：
  - physical_edges
  - process_edges
  - signal_edges
  - SceneBehaviorGraph
```

### 6.2 补全流程

1. **加载设备能力**：读取每个 `DeviceSpec` 的接口、端口、行为、信号和 runtime contract。
2. **计算端口世界坐标**：由 instance transform + physical interface local frame 得到所有候选连接点。
3. **推断 physical edges**：按距离、朝向、接口类型、物料类型生成候选边。
4. **派生 process edges**：从物理连接和用户目标中生成物料流路径。
5. **派生 signal edges**：根据设备行为契约补齐 `part_ready -> start_* -> *_done -> release` 等握手。
6. **编译 SceneBehaviorGraph**：生成事件、状态、行为规则、资源锁、完成条件和失败观测。
7. **运行 Guardian 校验**：检查所有引用、拓扑、端口方向、行为闭环、初始触发和目标可达。
8. **输出 patch 或追问**：高置信度补全直接暂存 patch，低置信度连接进入用户确认。

### 6.3 输出示例

```text
Agent 发现：
  - conveyor_1.exit 与 robot_1.pick_area 距离 0.18m，朝向兼容，物料类型 pallet 兼容，置信度 0.87。
  - robot_1.place_area 与 rack_1.cell_A2 距离 0.22m，置信度 0.76，需要用户确认。

Agent 生成候选：
  - physical_edges: conveyor_1.exit -> robot_1.pick_area
  - process_edges: conveyor_1.flow_output -> robot_1.flow_input -> rack_1.A2
  - signal_edges: conveyor_1.part_ready -> robot_1.start_pick
  - SceneBehaviorGraph: robot pick-place + rack putaway + timeout observation
```

---

## 7. Artifact 契约

Agent 不应直接写最终状态，应输出可校验 artifact。

| Artifact | 用途 | 是否可自动应用 |
|---|---|---:|
| `scene_patch` | 修改 instance、transform、param_overrides | 视风险而定 |
| `device_spec_patch` | 补设备端口、行为、信号、默认参数 | 通常需确认 |
| `physical_edge_patch` | 补物理接口边 | 高置信度可暂存，低置信度需确认 |
| `process_patch` | 补工艺流程边和模块 | 校验通过后可暂存 |
| `signal_patch` | 补信号边、trigger、timeout、transform | 校验通过后可暂存 |
| `scene_behavior_graph_patch` | 生成或修订 `SceneBehaviorGraph` | 校验通过后可写入候选版本 |
| `parameter_binding_patch` | 从文档或用户输入填参 | 低置信度需确认 |
| `diagnostic_report` | 查询、解释、报错根因 | 只读输出 |
| `question_set` | 缺失关键事实时追问 | 不写入 |
| `scenario_experiment_plan` | 多方案仿真比较 | 需用户或系统提交执行 |

所有可写 artifact 都必须包含：

```text
artifact_id
artifact_type
base_scene_revision
target_revision_policy
operations
reason
confidence
validation_report
source_trace
approval_required
rollback_hint
```

---

## 8. LangGraph 编排建议

建议主图如下：

```text
START
  -> LoadContextNode
  -> LoadDeviceCapabilitiesNode
  -> BuildOrLoadTopologyNode
  -> ClassifyIntentNode
  -> ResolveSlotsNode
  -> RouteTaskNode
      -> SceneQuerySubgraph
      -> ParameterFillSubgraph
      -> TopologyDiagnosisSubgraph
      -> ProcessCompileSubgraph
      -> BehaviorGraphCompileSubgraph
      -> RuntimeDiagnosisSubgraph
      -> ScenarioCompareSubgraph
  -> ValidateArtifactNode
  -> RepairOrInterruptNode
  -> ExplainNode
  -> StageOrApplyNode
  -> EmitResultNode
  -> END
```

关键控制规则：

- `BuildOrLoadTopologyNode` 是确定性工具节点，优先读缓存，revision 不匹配时重建。
- `ClassifyIntentNode` 和 `ResolveSlotsNode` 才开始使用 LLM。
- `ValidateArtifactNode` 必须是确定性工具节点。
- `RepairOrInterruptNode` 最多自动修复 2 次。
- `RuntimeDiagnosisSubgraph` 只由 observation、用户诊断请求或 interrupt 触发，不由普通 signal event 触发。
- `StageOrApplyNode` 必须执行 revision check 和 approval policy。

需要的 harness：

| Harness | 作用 |
|---|---|
| Schema harness | 所有 LLM 输出符合 Pydantic/JSON Schema。 |
| Tool harness | 工具输入输出、超时、副作用类型、幂等性明确。 |
| Revision harness | patch 绑定 base scene revision，写入前重检。 |
| Validation harness | 所有 artifact 入库或提交仿真前确定性校验。 |
| Repair harness | 限制自动修复次数，防止无界循环。 |
| Runtime harness | 长任务支持 pause/cancel/resume，observation 有统一格式。 |
| Replay harness | 保存节点事件、artifact、校验结果、用户确认，支持回放。 |
| Test harness | 用固定场景 fixture 验证最终 `SceneBehaviorGraph` 和诊断报告。 |

---

## 9. 验证能力设计

结合 `business.md` 中 VC 的有意义场景，Agent 侧验证不应只验证 JSON 合法，而要覆盖业务可用性。

### 9.1 布局验证

- 设备是否孤立。
- 端口是否悬空。
- 物理接口是否兼容。
- 是否存在明显方向错误。
- 机器人 pick/place 区域是否有候选可达性证据。

### 9.2 物流与节拍验证

- 物料从 source 到 sink 是否可达。
- 是否存在断链、环路或死循环。
- 下游满载时是否会 backpressure。
- 缓存容量是否建模。
- 投料节拍与处理节拍是否可能形成瓶颈。

### 9.3 机器人单元验证

- pick/place 行为是否由已存在行为能力支持。
- 机器人资源锁是否存在。
- 多机器人是否会抢同一物料。
- 抓取完成、放置完成、失败信号是否闭环。
- 路径/可达性第一阶段可先做几何近似，后续接 ROS/MoveIt 或机器人控制器。

### 9.4 虚拟调试 / PLC-like 验证

- 命令信号和状态信号方向是否正确。
- `start`、`running`、`done`、`error`、`reset` 是否有完整路线。
- signal latest value 和 event emit 是否区分。
- 外部 bridge 后期接入时，内部 signal port 能否映射 OPC UA / S7 地址。

### 9.5 运行时反馈验证

- 无可执行行为但任务未完成时，触发 deadlock observation。
- 行为超时，触发 timeout observation。
- 目标不可达，触发 target_not_reached observation。
- 资源锁长期占用，触发 resource_conflict 或 lock_timeout。
- 指标未达标，触发 metric_violation。

### 9.6 验收目标验证

- 用户或文档中的吞吐量目标是否转为 metric assertion。
- 仿真时长、 warm-up、统计窗口是否明确。
- 完成条件是否可计算。
- 如果输入数据不足，Agent 应报告“该验证不能成立”，而不是给出看似确定的结论。

---

## 10. 实施优先级

### P0：Agent 可用闭环

- `LoadContextNode`
- `LoadDeviceCapabilitiesNode`
- `BuildOrLoadTopologyNode`
- `ClassifyIntentNode`
- `ResolveSlotsNode`
- `SceneBehaviorGraphCompileSubgraph`
- `Guardian Validator`
- `scene_behavior_graph_patch` 输出
- agent event streaming

P0 的目标：用户给出自然语言目标后，Agent 能基于当前 `SceneDocument + DeviceSpec + TopologyGraph` 生成并校验 `SceneBehaviorGraph`，不参与实时高频控制。

### P1：替代 VC 人工建模的关键体验

- 隐式 physical/process edge 候选生成。
- 缺失 `signal_edges` 自动补全。
- 文档参数抽取和绑定。
- topology diagnosis 报告。
- runtime observation 根因分析。
- 自动修复 patch，最多 2 次闭环。
- 用户确认与低置信度候选交互。

P1 的目标：当 `SceneDocument` 只给位置或只有部分流程时，Agent 能补齐候选工艺、信号、行为图，并解释哪些是确定事实、哪些是假设。

### P2：形成“超越 VC”的差异化

- 多方案 scenario comparison。
- 产能、瓶颈、缓存容量、资源利用率自动解释。
- 根据仿真指标推荐布局或参数调整。
- 策略模板库和长期记忆。
- 测试驱动仿真验证：把验收文档转为 assertions。
- runtime observation -> repair patch -> pause/replan/resume 闭环。

P2 的目标：不只是让产线“跑起来”，而是让 Agent 帮用户判断“跑得是否合理、哪里不合理、怎么改”。

### P3：外部系统联动

- OPC UA bridge。
- Siemens S7 bridge。
- 机器人控制器 / ROS / MoveIt bridge。
- HIL/SIL 联调模式。
- 更高保真的机器人路径和碰撞验证。

P3 的目标：把内部信号运行时扩展到真实控制系统或更专业的运动学/控制验证工具。

---

## 11. 关键设计决策

### 11.1 拓扑由代码算，LLM 只解释和补全语义

端口遍历、空间邻近、方向匹配、连通分量、可达路径、拓扑排序、环路检测都应由确定性算法完成。LLM 负责解释结果、消解模糊用户表达、生成候选 patch 和说明假设。

### 11.2 Agent 输出 artifact，不直接覆盖事实源

所有修改必须先成为候选 artifact，再通过 schema、引用、拓扑、资源和 revision 校验。最终写入前根据 confidence 和 risk 决定自动应用、暂存或用户确认。

### 11.3 SceneBehaviorGraph 是核心建模产物

当前运行总线已经有 `SignalBusRuntime` 和设备行为执行链路。Agent 的主产物不应退回旧式 `SimPlan` 或脚本片段，而应聚焦生成 `SceneBehaviorGraph`，让 runtime 只消费结构化、可校验的行为图。

### 11.4 Runtime observation 是 Agent 再介入的边界

普通信号投递、状态推进、行为完成回调都留给 runtime。只有当 runtime 把异常升级为 observation，或用户主动请求诊断/修改/重规划时，Agent 才介入。

### 11.5 参数填充必须保留来源和置信度

从文档抽取的参数不能像手填属性那样丢失来源。每个参数都应有 source trace、单位归一、目标绑定和 confidence；关键参数低置信度时必须追问或作为假设展示。

---

## 12. 最小可落地模块组合

如果当前要尽快从“已有运行总线”推进到“Agent 可用”，建议最小实现顺序如下：

1. **Context Builder**：读取 `SceneDocument + DeviceSpec + TopologyGraph`，生成紧凑上下文。
2. **Intent Parser / Slot Resolver**：把用户目标解析为结构化 intent，并用拓扑摘要消解设备引用。
3. **Behavior Graph Compiler**：生成 `SceneBehaviorGraph` 的 events、states、rules、policies、completion、failure observations。
4. **Guardian Validator**：确定性校验 schema、引用、端口、拓扑和闭环。
5. **Repair Loop**：根据 validator 输出自动修复 1-2 次，仍失败则给诊断。
6. **Runtime Observation Diagnoser**：读取 observation + snapshot + event log，解释运行错误并生成修复候选。
7. **Topology Completion**：补齐“只有位置信息，没有路由”的候选 physical/process/signal edges。
8. **Parameter Filler**：从文档和自然语言中填充参数并绑定到 schema。

这个顺序能先把 Agent 的主闭环跑起来，再逐步覆盖 VC 人工操作中最痛的“连线、填参、排错、调参”。

---

## 13. 对现有文档的关系

- `docs/design/agent_design.md` 已经定义了 `SceneBehaviorGraph Agent` 的 LangGraph 节点细节；本文把范围扩展到“Agent 侧完整能力模块”，不只限于最终图生成。
- `docs/backend/agent_runtime_design.md` 已经明确 Agent 不做实时控制；本文延续该边界，把 runtime observation 作为 Agent 再介入点。
- `docs/research/vc_runtime_signal_schema_research.md` 已经给出 VC 信号、接口、runtime 的复刻清单；本文把其中 Agent 层扩展成可落地模块。
- `docs/research/vc_topology_agent_research.md` 重点讨论拓扑理解 Agent；本文将其纳入更大的“自动代理替代人工建模”体系。
- `docs/research/business.md` 说明 VC 的价值在布局、节拍、物流、机器人、PLC、方案验证；本文将这些价值映射为 Agent 的验证、诊断和方案比较能力。

---

## 14. 结论

Agent 侧的目标不是“让大模型直接调度设备运行”，也不是“把 VC 的手工流程编辑器换成聊天框”。真正要做的是把 VC 专家用户在建模过程中做的工作拆成可验证模块：

```text
看懂场景
  -> 补齐拓扑
  -> 填参数
  -> 编译工艺
  -> 编译信号
  -> 编译行为图
  -> 多层校验
  -> 提交 runtime
  -> 观察报错
  -> 解释并修复
```

这样 Agent 才能覆盖 VC 的核心工程价值：不是只播放动画，而是验证产线系统行为；同时又能超越 VC：不再要求用户手动配置每个流程、端口、信号、参数和脚本，而是由自动代理基于场景事实、设备能力、用户目标和运行反馈持续完成建模闭环。
