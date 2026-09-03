# SceneBehaviorGraph Agent 语义量化验证方法

> 目标：定义在实际验证过程中，如何把 Agent 生成的 `SceneBehaviorGraph` 与标准答案进行量化比对。本文重点解决“调度结果准确性”无法只靠字段名或 ID 精确匹配的问题，为论文实验验证和工程 benchmark 提供统一计算方法。

---

## 1. 问题定义

`SceneBehaviorGraph Agent` 的验证分为两类：

| 验证类型 | 方法 | 是否需要语义匹配 |
|---|---|---|
| 图合规性验证 | 脚本校验 JSON、schema、必填字段、引用完整性、旧字段污染 | 否 |
| 调度结果准确性验证 | 比较 Agent 输出图与标准答案图的工艺语义是否一致 | 是 |

图合规性可以通过确定性脚本完成，例如：

```text
json_parse_success
required_section_coverage
legacy_schema_violation_count
reference_error_count
```

真正困难的是调度结果准确性。原因是 `SceneBehaviorGraph` 中很多字段具有“语义等价但表面不同”的特点：

- 用户目标拆解结果可能措辞不同，但表达同一工艺意图。
- 模块名可能不同，例如 `parallel_sorting` 与 `robot_sorting_stage`。
- 事件名可能不同，例如 `pallet_ready` 与 `main_conveyor_2.arrived_at_sorting_position`。
- 状态变量名可能不同，例如 `workpiece_pool.remaining_parts` 与 `pallet_parts.unprocessed`。
- 行为规则可能拆分粒度不同，但触发条件、设备行为和状态效果等价。
- 策略函数可能命名不同，但都表达“谁空谁 claim”“满载 backpressure”“断点队列等待”。

因此，调度结果准确性不能使用简单 exact match，而应采用一套来自既有评测与图匹配研究的组合方法：

```text
结构标准化 + 语义单元抽取 + 多层匹配 + 加权评分
```

本文中的公式不是凭空定义的单一新指标，而是对以下成熟方法的组合改造：

- **信息检索评测**中的 Precision / Recall / F1，用于衡量期望语义单元是否被覆盖以及是否产生多余幻觉。
- **语义文本相似度**中的 embedding / cross-encoder / BERTScore 思路，用于比较模块描述、事件描述、guard/action 文本是否语义相近。
- **二分图最大权匹配 / Hungarian Algorithm**，用于解决 golden 单元与 prediction 单元名称不同、数量不同、顺序不同的问题。
- **图编辑距离、子图匹配与流程挖掘 conformance checking**，用于比较模块图、事件路由图、关键 trace 是否一致。
- **Rubric-based / LLM-as-a-Judge 评测**，用于难以用规则判断的语义等价，但只作为补充裁判，不替代确定性校验。
- **模型检查 / 不变量验证**，用于检查资源锁、重复 claim、死锁、完成条件可达等安全性和活性问题。

---

## 2. 可参考的现有验证方法

本节说明本文量化方案的来源。后续公式均标注为“复用”或“改造”：

- **复用**：直接采用已有研究或工程评测中的通用公式，例如 Precision / Recall / F1、Jaccard、LCS、最大权匹配。
- **改造**：将已有方法应用到 `SceneBehaviorGraph` 的特殊对象，例如把模块、事件、状态、行为规则抽取为语义单元后再计算 F1。

### 2.1 Agent / LLM 评测常用方法

| 方法 | 核心思想 | 本项目可借鉴点 |
|---|---|---|
| Golden Set Evaluation | 准备标准答案，用模型输出与标准答案对比 | 每个 case 维护 `scene_behavior_graph.golden.json` 和 `test_assertions.json` |
| Rubric-based Evaluation | 用评分规约对不同维度打分 | 对目标覆盖、模块、事件、状态、规则、策略分别评分 |
| LLM-as-a-Judge | 用强模型判断语义是否一致 | 用于目标覆盖、模块语义、规则意图等非 exact match 比对 |
| Semantic Similarity | 用 embedding / cross-encoder 判断文本语义相似 | 比较模块描述、事件描述、guard/action 语义 |
| Tool-use / Workflow Evaluation | 验证 Agent 是否调用正确工具并完成任务 | 本项目不以中间节点为主，但可借鉴“任务完成度”指标 |
| Pairwise / Preference Evaluation | 比较两个候选结果哪个更好 | 可用于论文中人工评价或消融实验 |
| Negative / Robustness Testing | 用错误、模糊、干扰输入验证鲁棒性 | 对 `negative_invalid` 和 `semantic_interference` case 评分 |

### 2.2 图结构与流程验证常用方法

| 方法 | 核心思想 | 本项目可借鉴点 |
|---|---|---|
| Graph Edit Distance | 计算两个图节点和边转换成本 | 用于模块图、事件路由图、行为依赖图相似度 |
| Subgraph Matching | 检查关键子图是否存在 | 检查“托盘运输 -> 分拣 -> 出料”关键链路 |
| Precision / Recall / F1 | 对期望元素和生成元素做集合匹配 | 适用于事件、状态变量、策略、规则等语义单元 |
| Ontology / Taxonomy Matching | 先归一到类型体系再匹配 | 将模块、事件、状态、策略归一到标准类别 |
| Trace-based Validation | 从起点事件静态 trace 到终点事件 | 验证事件链路和完成条件是否闭合 |
| Model Checking 思路 | 检查安全性、活性、不变量 | 验证不会重复 claim、资源锁释放、最终可完成 |

### 2.3 方法来源到本文指标的映射

| 本文指标 / 方法 | 采用的已有方法 | 使用方式 | 本项目改造点 |
|---|---|---|---|
| `Precision / Recall / F1` | 信息检索和分类评测通用指标 | 复用公式 | 将“相关文档 / 分类样本”替换为 `SceneBehaviorGraph` 语义单元 |
| `Jaccard` | 集合相似度 | 复用公式 | 用于设备集合、payload role 集合、状态类别集合 |
| `Embedding Similarity / BERTScore` | 语义文本相似度评测 | 复用思想 | 用于模块说明、事件说明、guard/action 自然语言片段 |
| `Cross-Encoder Similarity` | 语义匹配 / 检索重排 | 复用思想 | 用于判定两个规则或两个策略描述是否表达同一调度语义 |
| `Maximum Weight Bipartite Matching` | Hungarian Algorithm / assignment problem | 复用算法 | 用于 golden 单元和 prediction 单元的最优一对一匹配 |
| `Graph Edit Distance` | 图相似度计算 | 改造使用 | 用于模块图、事件路由图、行为依赖图的结构差异分析 |
| `Subgraph Matching` | VF2 等子图同构 / 子图匹配方法 | 改造使用 | 用于检查关键工艺子链路是否存在 |
| `LCS / Edit Distance` | 序列相似度 | 复用公式 | 用于比较事件 trace 和工艺阶段顺序 |
| `Process Mining Conformance Checking` | token replay / alignment-based conformance | 改造使用 | 用于判断预测事件链路是否符合 golden 行为流程 |
| `Rubric-based Evaluation` | G-Eval、MT-Bench、LLM Judge 等评测范式 | 改造使用 | 对目标覆盖、行为规则、策略语义设置维度化评分 |
| `Model Checking / Invariant Checking` | LTL/CTL safety/liveness 思路 | 改造使用 | 检查资源互斥、重复 claim、死锁、完成条件可达 |

### 2.4 推荐组合

本项目建议采用混合方法：

```text
Schema Exact Check
  + Semantic Unit Matching
  + Graph / Trace Similarity
  + Constraint / Invariant Check
  + Optional LLM Judge for ambiguous cases
```

其中：

- **确定性脚本**负责结构、引用、枚举、必填项。
- **语义匹配器**负责名称不同但含义相同的元素对齐。
- **图匹配 / trace**负责流程关系是否一致。
- **LLM Judge**只用于难以通过规则判断的语义等价，不作为唯一评分来源。

---

## 3. 统一评估对象

每个 case 的评估输入：

```text
input.md
scene_behavior_graph.golden.json
expected_answer.md
test_assertions.json
agent_output.scene_behavior_graph.json
```

记号定义：

| 符号 | 含义 |
|---|---|
| `G` | golden 标准行为图 |
| `P` | prediction，Agent 生成行为图 |
| `A` | `test_assertions.json` 中的断言集合 |
| `R` | 用户目标拆解出的需求集合 |
| `M` | 语义匹配矩阵 |
| `S_x` | 某个维度的分数 |

最终评分：

```text
Score_total = w_schema * S_schema + w_semantic * S_semantic
```

来源说明：该形式采用多指标评测中常见的 **weighted sum model / linear scalarization**。本文没有声称该公式是新的优化算法，而是把 schema 合规分与语义准确分线性汇总，便于工程 benchmark 和论文表格展示。权重需要通过验证集、专家标注或消融实验确定，不应被解释为普适常数。

由于图合规性较容易确定，论文实验中建议重点报告：

```text
S_semantic = weighted_sum(
  S_goal,
  S_module,
  S_event,
  S_route,
  S_state,
  S_rule,
  S_transition,
  S_policy,
  S_completion,
  S_failure
)
```

来源说明：`S_semantic` 的汇总方式同样来自多准则决策中的加权求和；每个子分数本身尽量采用已有评测指标，如 F1、Jaccard、LCS、最大匹配后的覆盖率。本文的创新点是把这些成熟指标映射到 `SceneBehaviorGraph` 的语义单元，而不是提出全新的数学指标。

---

## 4. 语义单元抽取

为了避免直接比较原始 JSON 字段名，需要先把 `SceneBehaviorGraph` 归一成可比较的语义单元。

### 4.1 语义单元类型

| 单元类型 | 来源 section | 归一化后的核心字段 |
|---|---|---|
| GoalRequirement | `goal`、`input.md`、`expected_answer.md` | `intent_type`、`object`、`action`、`constraint`、`expected_mapping` |
| ModuleUnit | `modules` | `mode`、`devices`、`material_flow_role`、`start_event`、`complete_event`、`description` |
| EventUnit | `event_bus.events` | `kind`、`source`、`semantic_role`、`payload_roles` |
| RouteUnit | `event_bus.routes` | `from_event_role`、`to_type`、`to_role`、`delivery`、`payload_flow` |
| StateUnit | `state_model` | `state_category`、`entity_scope`、`runtime_role` |
| BehaviorRuleUnit | `behavior_rules` | `trigger_role`、`guard_predicates`、`policy_type`、`action_type`、`target_device_type` |
| TransitionUnit | `state_transition_rules` | `trigger_type`、`effect_types`、`emitted_event_roles` |
| PolicyUnit | `policies` | `policy_type`、`problem_type`、`input_states`、`decision_output` |
| CompletionUnit | `completion_conditions` | `completion_predicates`、`dependent_states` |
| FailureUnit | `failure_observations` | `failure_type`、`trigger_condition`、`diagnostic_event` |

### 4.2 标准语义标签

建议为每类单元补充标准标签，避免只用自然语言比对。

示例标签：

```text
module_role:
  inbound_transport
  pallet_positioning
  robot_sorting
  robot_handoff
  machine_processing
  output_transport
  storage_inbound
  storage_outbound

state_category:
  device_state
  signal_value
  resource_lock
  active_action
  material_position
  workpiece_pool
  material_claim
  conveyor_load
  conveyor_stop_point
  conveyor_queue
  station_occupancy

policy_type:
  deterministic_priority
  shared_pool_claim
  load_balancing
  capacity_threshold
  nearest_available_stop_point
  downstream_release
  resource_lock
  queue_wait
  deadlock_detection
  timeout_retry
```

这些标签可以由以下方式得到：

1. 从 `test_assertions.json` 的 `must_have_*` 明确给出。
2. 从 golden 图字段和描述中规则抽取。
3. 使用 LLM 对模块、事件、规则做一次“只输出标签”的辅助标注。
4. 人工审核关键 case 的标签，作为论文实验 benchmark 固定答案。

---

## 5. 语义匹配方法

### 5.1 分层匹配顺序

对每一类语义单元，按以下顺序匹配 golden 与 prediction：

```text
1. Exact ID Match
2. Alias / Synonym Match
3. Typed Structural Match
4. Embedding Similarity Match
5. LLM Judge Match
```

| 层级 | 说明 | 例子 |
|---|---|---|
| Exact ID Match | ID 完全一致 | `robot.pick_done == robot.pick_done` |
| Alias Match | 经过别名表归一后一致 | `pallet_ready == arrived_at_sorting_position` |
| Typed Structural Match | 类型、设备、输入输出关系一致 | 两个模块都使用 robot + conveyor 完成分拣 |
| Embedding Match | 文本描述语义相似 | “谁空谁拿” 与 “idle robot claims next material” |
| LLM Judge Match | 对复杂规则进行判定 | 两套规则是否都实现 backpressure |

### 5.2 单元相似度公式

对任意 golden 单元 `g` 和预测单元 `p`，定义相似度：

```text
sim(g, p) = α * sim_id(g, p)
          + β * sim_type(g, p)
          + γ * sim_attribute(g, p)
          + δ * sim_relation(g, p)
          + ε * sim_text(g, p)
```

来源说明：该公式采用 **feature-based similarity / weighted similarity aggregation** 的通用形式，常见于实体对齐、schema matching、record linkage 和 ontology matching。本文将实体对齐中的“ID、类型、属性、关系、文本描述”特征映射到 `SceneBehaviorGraph` 单元。权重不是理论常数，需要在开发集上调参，或由专家给出并通过消融实验验证。

建议默认权重：

| 项 | 权重 | 含义 |
|---|---:|---|
| `sim_id` | 0.10 | ID 或别名相似度 |
| `sim_type` | 0.25 | 类型是否一致 |
| `sim_attribute` | 0.25 | 关键属性是否一致 |
| `sim_relation` | 0.25 | 与其他单元的连接关系是否一致 |
| `sim_text` | 0.15 | 文本语义相似度 |

其中：

```text
α + β + γ + δ + ε = 1
```

不同维度可以调整权重。例如事件路由更重视关系，策略函数更重视类型。

权重使用原则：

- 默认权重只作为起始配置。
- 论文实验中应报告权重设置，并提供消融实验或敏感性分析。
- 若没有足够数据调参，应采用等权或专家预注册权重，避免事后调权导致指标偏置。

### 5.3 二分图最大匹配

当模块名、事件名、规则名不一致时，不应逐 ID 比较，而应做集合匹配。

对某类单元：

```text
G_units = {g1, g2, ..., gm}
P_units = {p1, p2, ..., pn}
```

构造相似度矩阵：

```text
M[i][j] = sim(gi, pj)
```

然后使用最大权匹配：

```text
Match = max_weight_bipartite_matching(M)
```

来源说明：这里复用 **assignment problem / Hungarian Algorithm** 的最大权二分匹配形式。这样做的目的是避免模块名或事件名不同导致逐 ID 匹配失败，同时避免一个 prediction 单元重复匹配多个 golden 单元。

设匹配阈值为 `τ`：

```text
matched(gi, pj) = true if M[i][j] >= τ
```

推荐阈值：

| 单元类型 | 阈值 `τ` |
|---|---:|
| GoalRequirement | 0.75 |
| ModuleUnit | 0.70 |
| EventUnit | 0.70 |
| RouteUnit | 0.75 |
| StateUnit | 0.70 |
| BehaviorRuleUnit | 0.75 |
| TransitionUnit | 0.75 |
| PolicyUnit | 0.80 |
| CompletionUnit | 0.80 |
| FailureUnit | 0.75 |

---

## 6. 基础集合指标

匹配完成后，对每个维度计算 precision、recall、F1。

```text
TP = matched golden units count
FP = prediction units not matched to any golden unit
FN = golden units not matched by prediction

Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1        = 2 * Precision * Recall / (Precision + Recall)
```

来源说明：Precision / Recall / F1 直接复用信息检索、分类评测和抽取任务中的标准定义。本文仅把“相关文档 / 正类样本”替换为 golden 中的语义单元，把“检索结果 / 预测正例”替换为 prediction 中的语义单元。

解释：

- `Recall` 更重要：表示标准答案中的关键语义有没有被覆盖。
- `Precision` 也重要：表示 Agent 有没有幻觉出多余模块、事件、状态、策略。
- `F1` 用于整体平衡。

论文实验建议同时报告：

```text
SemanticRecall
SemanticPrecision
SemanticF1
HallucinationRate = FP / |P_units|
MissingRate       = FN / |G_units|
```

---

## 7. 各维度量化指标

### 7.1 用户目标覆盖度 `S_goal`

#### 7.1.1 目标需求抽取

先把用户目标拆成需求原子：

```json
{
  "requirement_id": "req_001",
  "type": "process_step | ordering | parallelism | constraint | exception | completion",
  "description": "两台机械臂共享托盘上的工件池，谁空闲谁抓取",
  "expected_mapping": ["modules", "behavior_rules", "policies", "state_model"]
}
```

#### 7.1.2 覆盖判定

一个需求 `r` 被覆盖，需满足：

```text
coverage(r) = max_semantic_match(r, P_related_units) >= τ_goal
```

其中 `P_related_units` 包括：

```text
modules + events + routes + state_model + behavior_rules + policies + completion_conditions + failure_observations
```

#### 7.1.3 公式

```text
S_goal = Σ weight(r) * coverage(r) / Σ weight(r)
```

来源说明：这是 **weighted recall / requirement coverage** 的形式，类似需求工程和测试覆盖中的加权需求覆盖率。本文将用户目标拆为需求原子后，以需求重要性作为权重计算覆盖率。

需求权重建议：

| 需求类型 | 默认权重 |
|---|---:|
| process_step | 1.0 |
| ordering | 1.2 |
| parallelism | 1.2 |
| constraint | 1.3 |
| exception | 1.3 |
| completion | 1.1 |

输出指标：

```text
goal_requirement_coverage = S_goal
missing_requirement_count = count(coverage(r) == 0)
constraint_mapping_accuracy = weighted coverage of constraint requirements
```

---

### 7.2 场景模块准确性 `S_module`

模块名可能不同，因此比较模块语义。

#### 7.2.1 模块相似度

```text
sim_module(g, p) = 0.20 * sim_mode
                 + 0.25 * sim_devices
                 + 0.20 * sim_material_flow_role
                 + 0.20 * sim_start_complete_events
                 + 0.15 * sim_description
```

来源说明：模块相似度采用 feature-based similarity。`sim_devices` 可直接使用 Jaccard；`sim_start_complete_events` 复用事件单元相似度；`sim_description` 可使用 embedding / cross-encoder / BERTScore 类语义相似度。各项权重是针对本任务的工程初始值，需要通过实验校准。

字段说明：

| 项 | 计算方法 |
|---|---|
| `sim_mode` | `sequential / parallel / continuous / parallel_continuous` 类型一致得 1，兼容类型得 0.5 |
| `sim_devices` | Jaccard(`golden.devices`, `prediction.devices`) |
| `sim_material_flow_role` | 模块角色标签相似度 |
| `sim_start_complete_events` | 起止事件语义匹配平均值 |
| `sim_description` | embedding 或 LLM judge 文本相似度 |

#### 7.2.2 指标

```text
module_coverage = Recall(ModuleUnit)
module_precision = Precision(ModuleUnit)
module_mapping_accuracy = F1(ModuleUnit)
```

模块顺序准确性：

先从模块的 `start_event / complete_event / routes` 构建偏序关系：

```text
Order_G = {(mi, mj) | mi should happen before mj in golden}
Order_P = {(mi, mj) | mi should happen before mj in prediction}
```

通过模块匹配关系投影后计算：

```text
module_order_accuracy = |Order_G ∩ Order_P| / |Order_G|
```

来源说明：该指标来自偏序关系一致性 / ordering accuracy 思路。它本质上是在比较 golden 与 prediction 中“阶段 A 必须先于阶段 B”的约束是否被保留。

并行准确性：

```text
parallel_module_accuracy = matched_parallel_relations / golden_parallel_relations
```

---

### 7.3 事件准确性 `S_event`

#### 7.3.1 事件相似度

```text
sim_event(g, p) = 0.25 * sim_kind
               + 0.20 * sim_source
               + 0.25 * sim_payload_schema
               + 0.20 * sim_event_role
               + 0.10 * sim_name_or_description
```

来源说明：事件相似度采用 schema matching 中的字段级加权相似度。`kind/source/payload_schema` 是结构特征，`event_role/name/description` 是语义特征。

其中：

```text
sim_payload_schema = F1(payload_roles_g, payload_roles_p)
```

来源说明：payload 比较复用集合 F1，但比较对象不是原字段名，而是归一化后的 payload role。这是对信息抽取 slot filling 评测的改造。

payload 字段不要只比字段名，而要归一到角色：

```text
robot_id -> actor_device
conveyor_id -> target_conveyor
material_id -> material
current_load -> load_value
max_capacity -> capacity_limit
```

#### 7.3.2 指标

```text
event_registration_completeness = Recall(EventUnit)
event_precision = Precision(EventUnit)
event_semantic_f1 = F1(EventUnit)
payload_reference_validity = valid_payload_refs / total_payload_refs
```

---

### 7.4 事件路由准确性 `S_route`

路由比事件更强调关系，不能只看 route_id。

#### 7.4.1 路由相似度

```text
sim_route(g, p) = 0.25 * sim_from_event
               + 0.20 * sim_to_type
               + 0.20 * sim_to_target
               + 0.15 * sim_delivery
               + 0.20 * sim_payload_flow
```

来源说明：路由相似度来自关系抽取 / 图边匹配的特征聚合方法。边的相似度由起点、终点、边类型和携带属性共同决定。

说明：

| 项 | 含义 |
|---|---|
| `sim_from_event` | from 事件语义是否相同 |
| `sim_to_type` | `rule / topic / runtime / device / module` 是否一致 |
| `sim_to_target` | 目标消费者语义是否相同 |
| `sim_delivery` | `direct / broadcast / internal` 是否一致 |
| `sim_payload_flow` | 投递参数是否支撑下游 trigger / guard / action |

#### 7.4.2 关键链路 trace

事件路由还要做静态 trace：

```text
runtime.sim_start
  -> ...
  -> key business events
  -> completion event / completion checker
```

定义 golden 关键链路集合：

```text
Trace_G = {trace_1, trace_2, ..., trace_k}
Trace_P = traces derived from prediction event_bus + behavior_rules + transition emits
```

链路相似度：

```text
trace_similarity(tg, tp) = LCS(event_roles_tg, event_roles_tp) / len(event_roles_tg)
```

来源说明：该公式直接复用序列相似度中的 **Longest Common Subsequence (LCS)**，用于比较两个事件 trace 是否保留关键事件顺序。它与流程挖掘 conformance checking 中的 trace alignment 思路一致，但这里先采用更轻量的 LCS 近似。

事件链路完整度：

```text
event_chain_completeness = average(max trace_similarity(tg, tp) for tg in Trace_G)
```

#### 7.4.3 指标

```text
route_semantic_accuracy = F1(RouteUnit)
event_chain_completeness = average best trace similarity
topic_subscription_coverage = matched_topic_subscriptions / golden_topic_subscriptions
```

---

### 7.5 状态模型准确性 `S_state`

状态变量名可能不同，因此按状态类别和用途匹配。

#### 7.5.1 状态相似度

```text
sim_state(g, p) = 0.30 * sim_state_category
               + 0.25 * sim_entity_scope
               + 0.20 * sim_runtime_role
               + 0.15 * sim_used_by_rules
               + 0.10 * sim_name_or_description
```

来源说明：状态变量比较采用 ontology matching / schema matching 的方法。先将状态变量归一到状态类别，再比较作用范围、运行时用途和被规则使用情况。

状态类别示例：

```text
device_state
signal_value
resource_lock
active_action
material_position
workpiece_pool
material_claim
conveyor_stop_point
conveyor_occupancy
conveyor_queue
conveyor_load
station_occupancy
```

#### 7.5.2 指标

```text
state_variable_coverage = Recall(StateUnit)
state_precision = Precision(StateUnit)
state_model_f1 = F1(StateUnit)
runtime_readiness_score = weighted coverage of required runtime state categories
```

`runtime_readiness_score` 公式：

```text
runtime_readiness_score = Σ weight(c) * has_state_category(c) / Σ weight(c)
```

来源说明：该指标来自 checklist coverage / weighted coverage。它不是新的相似度算法，而是用加权覆盖率衡量 Runtime 初始化所需状态类别是否齐全。

传送带场景建议提高以下状态权重：

```text
conveyor_stop_point
conveyor_occupancy
conveyor_queue
conveyor_load
```

---

### 7.6 行为规则准确性 `S_rule`

行为规则是事件、状态、策略、设备行为的组合，需要复合评分。

#### 7.6.1 规则相似度

```text
sim_rule(g, p) = 0.20 * sim_trigger
              + 0.20 * sim_guard
              + 0.20 * sim_policy
              + 0.25 * sim_action
              + 0.15 * sim_module_context
```

来源说明：行为规则相似度采用 structured prediction / semantic parsing 评测中常见的 component-wise scoring。一个规则被拆成 trigger、guard、policy、action、context 五个可解释子结构分别评分。

子项定义：

| 子项 | 计算方式 |
|---|---|
| `sim_trigger` | trigger event 的事件语义相似度 |
| `sim_guard` | guard predicate 集合 F1 + 文本语义相似 |
| `sim_policy` | policy type 和 policy problem 相似度 |
| `sim_action` | action type、设备类型、behavior_id 语义相似 |
| `sim_module_context` | 所属模块语义匹配 |

#### 7.6.2 guard 谓词归一化

将 guard 表达式归一为谓词：

```text
device_idle(robot_1)
material_available(workpiece_pool)
capacity_available(conveyor)
resource_unlocked(robot.gripper)
stop_point_available(conveyor)
not_blocked(target_conveyor)
```

比较：

```text
sim_guard = F1(predicate_set_g, predicate_set_p)
```

来源说明：guard 比较复用逻辑谓词集合的 Precision / Recall / F1，类似 semantic parsing 中对 logical form predicate 的组件级评测。本文将自然语言或表达式 guard 先归一为谓词集合。

#### 7.6.3 指标

```text
trigger_validity = matched_trigger_count / golden_trigger_count
guard_relevance = average sim_guard over matched rules
policy_relevance = average sim_policy over matched rules
action_validity = average sim_action over matched rules
behavior_rule_accuracy = F1(BehaviorRuleUnit)
```

---

### 7.7 状态迁移准确性 `S_transition`

状态迁移关注 effects 是否能推进流程闭环。

#### 7.7.1 effect 类型归一化

将 effects 归一为类型：

```text
set_device_state
add_active_action
remove_active_action
acquire_resource_lock
release_resource_lock
move_material
update_material_position
update_conveyor_load
occupy_stop_point
release_stop_point
update_workpiece_pool
create_material_claim
clear_material_claim
emit_event
emit_observation
```

#### 7.7.2 迁移相似度

```text
sim_transition(g, p) = 0.20 * sim_trigger_type
                    + 0.35 * F1(effect_types_g, effect_types_p)
                    + 0.25 * F1(emitted_event_roles_g, emitted_event_roles_p)
                    + 0.20 * sim_dependent_states
```

来源说明：状态迁移比较借鉴 plan/action model evaluation 的 effect matching：比较动作或事件触发后对状态的增删改效果是否一致。`effect_types` 和 `emitted_event_roles` 用集合 F1 计算。

#### 7.7.3 指标

```text
transition_effect_coverage = Recall(TransitionUnit)
emitted_event_registration_rate = registered_emitted_events / emitted_events
resource_release_completeness = matched_release_effects / golden_release_effects
completion_state_reachability = reachable_completion_states / golden_completion_states
```

---

### 7.8 策略函数适配度 `S_policy`

策略名称可能不同，但策略类型和解决的问题必须一致。

#### 7.8.1 策略相似度

```text
sim_policy(g, p) = 0.40 * sim_policy_type
                + 0.25 * sim_problem_type
                + 0.20 * sim_input_states
                + 0.15 * sim_decision_output
```

来源说明：策略函数比较采用 ontology/type matching + input/output behavior matching。策略类型是最重要特征，因此权重最高；输入状态和决策输出用于确认该策略是否真的解决同一调度问题。

其中：

- `sim_policy_type`：`shared_pool_claim`、`capacity_threshold` 等类型是否一致。
- `sim_problem_type`：是否解决同一类调度问题。
- `sim_input_states`：是否读取相同状态类别。
- `sim_decision_output`：是否产生相同决策，例如 claim、pause、resume、select target。

#### 7.8.2 指标

```text
policy_selection_accuracy = Recall(PolicyUnit)
policy_precision = Precision(PolicyUnit)
policy_parameter_correctness = average sim_input_states over matched policies
dynamic_conflict_coverage = covered_dynamic_conflict_types / golden_dynamic_conflict_types
```

动态冲突类型：

```text
shared_material_conflict
resource_mutex_conflict
capacity_conflict
stop_point_occupancy_conflict
downstream_block_conflict
deadlock_risk
timeout_risk
```

---

### 7.9 完成条件准确性 `S_completion`

完成条件需要关注是否可判定、是否覆盖目标终点。

```text
sim_completion(g, p) = 0.35 * F1(predicate_types_g, predicate_types_p)
                    + 0.25 * sim_dependent_states
                    + 0.25 * sim_goal_success_criteria
                    + 0.15 * sim_checkability
```

来源说明：完成条件比较复用谓词集合 F1，并加入可判定性 checkability。可判定性来自模型检查和运行时监控中的“条件是否能由状态变量求值”要求。

指标：

```text
completion_condition_accuracy = F1(CompletionUnit)
completion_condition_checkability = checkable_conditions / total_conditions
completion_goal_alignment = matched_success_criteria / golden_success_criteria
```

---

### 7.10 异常观测准确性 `S_failure`

```text
sim_failure(g, p) = 0.35 * sim_failure_type
                 + 0.25 * sim_trigger_condition
                 + 0.20 * sim_diagnostic_event
                 + 0.20 * sim_recovery_or_report_action
```

来源说明：异常观测比较采用 event/diagnostic matching。failure type 类似分类标签，trigger condition 类似谓词集合，diagnostic event 类似事件匹配。

指标：

```text
failure_observation_coverage = Recall(FailureUnit)
failure_precision = Precision(FailureUnit)
negative_case_handling_rate = correctly_reported_invalid_cases / total_negative_cases
```

---

## 8. 总分计算

### 8.1 语义准确性总分

推荐权重：

| 维度 | 符号 | 权重 |
|---|---|---:|
| 用户目标覆盖度 | `S_goal` | 0.18 |
| 场景模块准确性 | `S_module` | 0.12 |
| 事件准确性 | `S_event` | 0.10 |
| 事件路由准确性 | `S_route` | 0.12 |
| 状态模型准确性 | `S_state` | 0.10 |
| 行为规则准确性 | `S_rule` | 0.16 |
| 状态迁移准确性 | `S_transition` | 0.10 |
| 策略函数适配度 | `S_policy` | 0.12 |
| 完成条件准确性 | `S_completion` | 0.06 |
| 异常观测准确性 | `S_failure` | 0.04 |

权重来源说明：该权重不是来自外部固定标准，而是本项目基于任务重要性的专家初始权重。使用时应在论文中明确声明为 **expert-defined weights**，并通过以下方式增强可信度：

1. 报告各子指标的单独分数，不只报告总分。
2. 增加等权重版本作为对照。
3. 做权重敏感性分析，例如每个权重上下浮动 20%。
4. 在消融实验中验证行为规则、策略、trace 等关键维度的贡献。

公式：

```text
S_semantic = 0.18*S_goal
           + 0.12*S_module
           + 0.10*S_event
           + 0.12*S_route
           + 0.10*S_state
           + 0.16*S_rule
           + 0.10*S_transition
           + 0.12*S_policy
           + 0.06*S_completion
           + 0.04*S_failure
```

### 8.2 按 case 类型调整权重

不同 case 类型重点不同：

| Case 类型 | 权重调整 |
|---|---|
| `positive_basic` | 提高 `S_goal`、`S_module`、`S_route` |
| `parallel_collaboration` | 提高 `S_rule`、`S_policy`、`S_state` |
| `continuous_discrete_event` | 提高 `S_state`、`S_transition`、`S_route` |
| `negative_invalid` | 提高 `S_failure` 和 `negative_case_handling_rate` |
| `semantic_interference` | 提高 `S_goal`、`legacy_schema_violation_rate`、`hallucination_rate` |

### 8.3 最终通过条件

建议通过标准：

```text
schema_valid == true
S_semantic >= 0.80
S_goal >= 0.85
S_rule >= 0.75
S_policy >= 0.75
critical_missing_count == 0
```

其中 `critical_missing_count` 包括：

- 缺少核心流程模块。
- 缺少关键事件链路。
- 缺少必要状态变量。
- 缺少关键策略，例如 backpressure、shared_pool_claim、resource_lock。
- 完成条件不可判定。

---

## 9. LLM Judge 的使用方式

### 9.1 使用边界

LLM Judge 适合判断：

- 用户目标是否被等价覆盖。
- 模块语义是否一致。
- 行为规则是否表达同一调度意图。
- 策略是否解决同一类动态问题。

LLM Judge 不适合判断：

- JSON 是否可解析。
- 字段是否存在。
- 引用是否存在。
- 事件 ID 是否注册。

这些必须用脚本确定性验证。

### 9.2 Judge 输入格式

```json
{
  "dimension": "behavior_rule_accuracy",
  "golden_unit": {...},
  "prediction_unit": {...},
  "rubric": {
    "trigger_equivalence": 0.2,
    "guard_equivalence": 0.2,
    "policy_equivalence": 0.2,
    "action_equivalence": 0.25,
    "module_context_equivalence": 0.15
  },
  "question": "Are these two behavior rules semantically equivalent for the simulation scheduling task? Return JSON only."
}
```

Judge 输出：

```json
{
  "score": 0.0,
  "matched": false,
  "reason": "...",
  "subscores": {
    "trigger_equivalence": 0.0,
    "guard_equivalence": 0.0,
    "policy_equivalence": 0.0,
    "action_equivalence": 0.0,
    "module_context_equivalence": 0.0
  }
}
```

### 9.3 降低主观性的策略

- Judge 只输出 JSON，不输出自由文本长解释。
- 每个维度给清晰 rubric。
- 对同一 pair 可多次采样取平均，或使用两个 judge 模型取一致性。
- 低置信度样本进入人工复核。
- 论文中报告 judge agreement，例如 Cohen's Kappa 或 pairwise agreement。

---

## 10. 工程实现建议

### 10.1 评估流水线

```text
1. load golden graph G
2. load prediction graph P
3. run schema validator
4. extract semantic units from G and P
5. normalize units with taxonomy and alias table
6. compute pairwise similarity matrix for each unit type
7. run maximum bipartite matching
8. compute precision / recall / F1 per dimension
9. run graph trace checks
10. run invariant checks
11. aggregate weighted score
12. write validation_report.md and benchmark_summary.md
```

### 10.2 推荐产物

```text
docs/test/validate/
  method/
    semantic_quantitative_evaluation.md
  alias/
    event_aliases.json
    state_aliases.json
    policy_aliases.json
  taxonomy/
    semantic_tags.json
  reports/
    scene_XX_case_YY.validation_report.md
    benchmark_summary.md
```

### 10.3 需要维护的辅助表

#### 事件别名表

```json
{
  "pallet_ready": [
    "arrived_at_sorting_position",
    "main_conveyor_2.pallet_ready",
    "pallet_arrived"
  ]
}
```

#### 状态类别表

```json
{
  "workpiece_pool": [
    "remaining_parts",
    "unprocessed_parts",
    "pallet_parts"
  ],
  "conveyor_load": [
    "current_load",
    "occupancy_count",
    "buffer_load"
  ]
}
```

#### 策略问题表

```json
{
  "shared_material_conflict": ["shared_pool_claim", "resource_lock"],
  "capacity_conflict": ["capacity_threshold", "backpressure"],
  "stop_point_occupancy_conflict": ["queue_wait", "nearest_available_stop_point"]
}
```

---

## 11. 论文实验呈现建议

### 11.1 实验问题

可以设置以下研究问题：

| RQ | 问题 |
|---|---|
| RQ1 | Agent 是否能生成 schema 合规的 `SceneBehaviorGraph`？ |
| RQ2 | Agent 是否能覆盖用户目标中的关键工艺要求？ |
| RQ3 | Agent 是否能正确建模事件、状态、规则和策略之间的调度语义？ |
| RQ4 | Agent 是否能处理并行协作、连续状态离散化、异常与语义干扰？ |
| RQ5 | 语义匹配评估方法是否比 exact match 更合理地区分正确输出与表面差异？ |

### 11.2 指标表

建议论文报告：

```text
SchemaPassRate
SemanticF1
GoalCoverage
ModuleF1
EventRouteF1
StateModelF1
BehaviorRuleF1
TransitionF1
PolicyF1
CompletionAccuracy
FailureCoverage
HallucinationRate
NegativeCaseHandlingRate
```

### 11.3 消融实验

可设计：

| 实验 | 目的 |
|---|---|
| exact match only | 证明字段名精确匹配对语义输出不公平 |
| without alias table | 评估别名归一化的贡献 |
| without LLM judge | 评估规则 + embedding 是否足够 |
| without trace check | 评估只做集合匹配是否忽略流程闭环 |
| without policy matching | 评估策略函数对调度语义的重要性 |

---

## 12. 小结

调度结果准确性应采用“语义单元级”量化比对，而不是直接比较 JSON 字段名。

推荐核心方法是：

```text
语义单元抽取
  -> 类型与别名归一化
  -> 单元相似度计算
  -> 二分图最大匹配
  -> Precision / Recall / F1
  -> trace 与 invariant 补充校验
  -> 加权总分
```

这种方法既能保留脚本验证的可重复性，也能处理自然语言 Agent 输出中常见的命名差异、粒度差异和表达差异，更适合作为论文实验中的量化验证方法。

---

## 13. 参考来源与检索关键词

本文方法可以在论文中引用或对齐以下研究方向。这里给出可直接进入论文相关工作或方法依据的典型学术来源，同时保留检索关键词，方便后续补 BibTeX。

### 13.1 信息检索与分类评测

用于支持 Precision / Recall / F1、加权覆盖率、幻觉率和缺失率。

典型引用：

- Manning, C. D., Raghavan, P., & Schütze, H. (2008). *Introduction to Information Retrieval*. Cambridge University Press.
- Powers, D. M. W. (2011). Evaluation: From Precision, Recall and F-Measure to ROC, Informedness, Markedness and Correlation. *Journal of Machine Learning Technologies*, 2(1), 37–63.
- Van Rijsbergen, C. J. (1979). *Information Retrieval* (2nd ed.). Butterworths.

检索关键词：

```text
information retrieval precision recall f1
classification evaluation precision recall f1
weighted recall requirement coverage
```

### 13.2 语义文本相似度

用于支持模块描述、事件描述、guard/action 描述的语义相似度。

典型引用：

- Agirre, E., Diab, M., Cer, D., & Gonzalez-Agirre, A. (2012). SemEval-2012 Task 6: A Pilot on Semantic Textual Similarity. *Proceedings of SemEval 2012*.
- Zhang, T., Kishore, V., Wu, F., Weinberger, K. Q., & Artzi, Y. (2020). BERTScore: Evaluating Text Generation with BERT. *International Conference on Learning Representations (ICLR)*.
- Reimers, N., & Gurevych, I. (2019). Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks. *Proceedings of EMNLP-IJCNLP 2019*.
- Cer, D., Yang, Y., Kong, S.-Y., et al. (2018). Universal Sentence Encoder. *Proceedings of EMNLP 2018: System Demonstrations*.

检索关键词：

```text
semantic textual similarity STS
BERTScore text generation evaluation
sentence embedding similarity evaluation
cross encoder semantic similarity
```

### 13.3 实体对齐、Schema Matching 与 Ontology Matching

用于支持 feature-based similarity、字段归一化、状态变量类别匹配、payload role 匹配。

典型引用：

- Rahm, E., & Bernstein, P. A. (2001). A survey of approaches to automatic schema matching. *The VLDB Journal*, 10, 334–350.
- Euzenat, J., & Shvaiko, P. (2013). *Ontology Matching* (2nd ed.). Springer.
- Doan, A., Halevy, A., & Ives, Z. (2012). *Principles of Data Integration*. Morgan Kaufmann.
- Fellegi, I. P., & Sunter, A. B. (1969). A Theory for Record Linkage. *Journal of the American Statistical Association*, 64(328), 1183–1210.
- Christen, P. (2012). *Data Matching: Concepts and Techniques for Record Linkage, Entity Resolution, and Duplicate Detection*. Springer.

检索关键词：

```text
schema matching feature based similarity
ontology matching entity alignment
record linkage weighted similarity
data integration schema matching survey
```

### 13.4 二分图匹配与 Assignment Problem

用于支持 golden 单元与 prediction 单元的一对一最大权匹配。

典型引用：

- Kuhn, H. W. (1955). The Hungarian Method for the Assignment Problem. *Naval Research Logistics Quarterly*, 2(1–2), 83–97.
- Munkres, J. (1957). Algorithms for the Assignment and Transportation Problems. *Journal of the Society for Industrial and Applied Mathematics*, 5(1), 32–38.
- Burkard, R. E., Dell'Amico, M., & Martello, S. (2009). *Assignment Problems*. SIAM.

检索关键词：

```text
Hungarian algorithm assignment problem
maximum weight bipartite matching
linear sum assignment semantic matching
```

### 13.5 图相似度与图匹配

用于支持模块图、事件路由图、行为依赖图的结构相似度。

典型引用：

- Sanfeliu, A., & Fu, K.-S. (1983). A distance measure between attributed relational graphs for pattern recognition. *IEEE Transactions on Systems, Man, and Cybernetics*, 13(3), 353–362.
- Bunke, H. (1997). On a relation between graph edit distance and maximum common subgraph. *Pattern Recognition Letters*, 18(8), 689–694.
- Riesen, K., & Bunke, H. (2009). Approximate graph edit distance computation by means of bipartite graph matching. *Image and Vision Computing*, 27(7), 950–959.
- Cordella, L. P., Foggia, P., Sansone, C., & Vento, M. (2004). A (Sub)Graph Isomorphism Algorithm for Matching Large Graphs. *IEEE Transactions on Pattern Analysis and Machine Intelligence*, 26(10), 1367–1372.

检索关键词：

```text
graph edit distance graph similarity
subgraph matching VF2 algorithm
workflow graph similarity
process graph matching
```

### 13.6 流程挖掘与 Conformance Checking

用于支持 trace-based validation、事件序列对齐、流程顺序一致性。

典型引用：

- van der Aalst, W. M. P. (2016). *Process Mining: Data Science in Action* (2nd ed.). Springer.
- Adriansyah, A., van Dongen, B. F., & van der Aalst, W. M. P. (2011). Conformance Checking Using Cost-Based Fitness Analysis. *IEEE International Enterprise Distributed Object Computing Conference (EDOC)*.
- Adriansyah, A., van Dongen, B. F., & van der Aalst, W. M. P. (2011). Towards Robust Conformance Checking. *Business Process Management Workshops*.
- Carmona, J., van Dongen, B., Solti, A., & Weidlich, M. (2018). *Conformance Checking: Relating Processes and Models*. Springer.

检索关键词：

```text
process mining conformance checking
trace alignment process mining
token replay conformance checking
event log trace alignment
```

### 13.7 模型检查与不变量验证

用于支持资源锁、重复 claim、死锁、完成条件可达等 safety / liveness 验证。

典型引用：

- Clarke, E. M., & Emerson, E. A. (1981). Design and synthesis of synchronization skeletons using branching time temporal logic. *Workshop on Logic of Programs*.
- Queille, J.-P., & Sifakis, J. (1982). Specification and Verification of Concurrent Systems in CESAR. *International Symposium on Programming*.
- Clarke, E. M., Grumberg, O., & Peled, D. A. (1999). *Model Checking*. MIT Press.
- Baier, C., & Katoen, J.-P. (2008). *Principles of Model Checking*. MIT Press.

检索关键词：

```text
model checking safety liveness invariants
LTL CTL model checking workflow verification
deadlock detection resource allocation model checking
```

### 13.8 LLM-as-a-Judge 与 Rubric-based Evaluation

用于支持语义等价的补充判断，但不替代脚本验证。

典型引用：

- Liu, Y., Iter, D., Xu, Y., Wang, S., Xu, R., & Zhu, C. (2023). G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment. *Proceedings of EMNLP 2023*.
- Zheng, L., Chiang, W.-L., Sheng, Y., et al. (2023). Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena. *Advances in Neural Information Processing Systems (NeurIPS) Datasets and Benchmarks Track*.
- Chiang, W.-L., Zheng, L., Sheng, Y., et al. (2024). Chatbot Arena: An Open Platform for Evaluating LLMs by Human Preference. *Proceedings of ICML 2024*.
- Novikova, J., Dušek, O., Curry, A. C., & Rieser, V. (2017). Why We Need New Evaluation Metrics for NLG. *Proceedings of EMNLP 2017*.

检索关键词：

```text
LLM as a judge evaluation
G-Eval NLG evaluation
MT-Bench LLM judge
rubric based evaluation language models
LLM evaluator agreement Cohen kappa
```

### 13.9 Agent Benchmark 与 Tool-use Evaluation

用于支持 Agent 任务完成度、workflow 输出质量、鲁棒性 case 设计。

典型引用：

- Yao, S., Zhao, J., Yu, D., et al. (2023). ReAct: Synergizing Reasoning and Acting in Language Models. *International Conference on Learning Representations (ICLR)*.
- Qin, Y., Liang, S., Ye, Y., et al. (2023). ToolLLM: Facilitating Large Language Models to Master 16000+ Real-world APIs. *arXiv preprint arXiv:2307.16789*.
- Liu, X., Yu, H., Zhang, H., et al. (2023). AgentBench: Evaluating LLMs as Agents. *International Conference on Learning Representations (ICLR) 2024*.
- Jimenez, C. E., Yang, J., Wettig, A., et al. (2024). SWE-bench: Can Language Models Resolve Real-World GitHub Issues? *International Conference on Learning Representations (ICLR)*.
- Zhou, S., Xu, F. F., Zhu, H., et al. (2023). WebArena: A Realistic Web Environment for Building Autonomous Agents. *International Conference on Learning Representations (ICLR) 2024*.

检索关键词：

```text
agent benchmark tool use evaluation
workflow agent evaluation benchmark
LLM agent task success rate
negative robustness evaluation language agents
```

### 13.10 本文方法定位

本文方法不是提出一个脱离已有研究的全新指标，而是将上述成熟评测方法组合并映射到 `SceneBehaviorGraph`：

```text
信息检索指标
  -> 语义单元覆盖率、幻觉率、缺失率

schema / ontology matching
  -> 模块、事件、状态、策略的语义对齐

二分图最大权匹配
  -> 名称不同、数量不同情况下的一对一单元匹配

流程挖掘 conformance checking
  -> 事件链路和工艺顺序一致性

模型检查
  -> 资源互斥、死锁、完成条件可达

LLM-as-a-Judge
  -> 难以规则化的语义等价补充判断
```

论文表述时应明确：公式中的权重和标签体系是面向自然语言驱动仿真工艺建模任务的工程化适配，基础计算方法来自已有研究。
