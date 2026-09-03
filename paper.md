LLM&Agent 量化评估
有，建议你按三类引用：LLM Agent 量化评估、LLM 生成结果量化评估、结构化/图结果语义比对评估。你的 SceneBehaviorGraph 验证最适合组合这三类。
LLM Agent 量化评估
- 📌 AgentBench: Evaluating LLMs as Agents
  适合引用“Agent 能力可拆成多任务环境，用任务成功率、完成率、交互轮次、效率等指标量化”。你的 Agent 不是只生成文本，而是完成一个场景建模任务，可以借鉴它的 benchmark 设计。
- 📌 WebArena: A Realistic Web Environment for Building Autonomous Agents
  适合引用“在真实环境中评估 Agent 的任务完成率”。虽然它是 Web Agent，但思路类似：给定任务目标，看 Agent 是否生成能完成任务的操作链路。
- 📌 Mind2Web: Towards a Generalist Agent for the Web
  适合引用“把 Agent 行为拆成 action selection、element selection、operation prediction 等可量化子任务”。你的场景里也可以拆成模块选择、事件选择、状态变量选择、行为规则选择。
- 📌 ToolLLM: Facilitating Large Language Models to Master 16000+ Real-world APIs
  适合引用工具调用型 Agent 的评估方式：tool selection、参数生成、任务完成率。你的 Agent 也需要选择设备行为、策略函数和事件路由，可以借鉴它的分项指标。
- 📌 SWE-bench: Can Language Models Resolve Real-World GitHub Issues?
  适合引用“用真实任务 + 可执行测试判断结果是否正确”。你的 SceneBehaviorGraph 也可以通过 schema 校验、语义断言、trace 校验来判断是否通过。
- 📌 GAIA: A Benchmark for General AI Assistants
  适合引用通用 Agent 的多步推理、工具使用、真实任务完成率。你的 Agent 也属于多步结构化任务：理解场景、规划行为、生成图、校验图。
- 📌 OSWorld: Benchmarking Multimodal Agents for Open-Ended Tasks in Real Computer Environments
  适合引用“多模态 Agent 在真实环境中的任务成功率、步骤效率、操作正确性”。你这里也有场景图片参与理解，可以借鉴它的多模态 Agent 评估思路。
- 📌 ReAct: Synergizing Reasoning and Acting in Language Models
  适合引用 Agent 推理-行动循环的思想。虽然不是专门评估论文，但可用于说明 Agent 任务需要分步骤 reasoning，并对每步结果做验证。
LLM 生成结果量化评估
- 📌 BLEU: a Method for Automatic Evaluation of Machine Translation
  适合引用最早期的自动生成结果量化评估方法。它基于 n-gram overlap，但对你的项目只能作为“传统 exact / surface match 不够”的反例或 baseline。
- 📌 ROUGE: A Package for Automatic Evaluation of Summaries
  适合引用文本生成结果的 recall-oriented overlap 评估。可作为说明：简单文本重叠适合摘要，不适合你的行为图语义验证。
- 📌 METEOR: An Automatic Metric for MT Evaluation with Improved Correlation with Human Judgments
  适合引用“引入词形、同义词、语义匹配，比 BLEU 更柔性”。你的事件名、模块名不同但语义相近，和 METEOR 的思想类似。
- 📌 BERTScore: Evaluating Text Generation with BERT
  适合引用“用 contextual embedding 做语义相似度，而不是只看字符或词重叠”。你的模块描述、规则描述、目标覆盖度可以借鉴 BERTScore 思路。
- 📌 BLEURT: Learning Robust Metrics for Text Generation
  适合引用“学习式评估指标，比传统 overlap 更接近人工判断”。如果你后续想训练或微调一个评估器，可以借鉴。
- 📌 MoverScore: Text Generation Evaluating with Contextualized Embeddings and Earth Mover Distance
  适合引用“用语义 token 分布距离评估生成文本”。可作为你做模块/事件描述语义距离的参考。
- 📌 BARTScore: Evaluating Generated Text as Text Generation
  适合引用“用预训练生成模型计算候选文本与参考文本之间的生成概率”。可作为语义相似度评估的另一类参考。
- 📌 G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment
  适合引用 LLM-as-a-Judge 和 rubric-based evaluation。你的行为规则、策略语义、目标覆盖度可以用 rubric 让 LLM 辅助评分。
- 📌 Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena
  适合引用“LLM 可以作为评估器，但需要控制偏差和一致性”。你的方案里 LLM Judge 应作为补充，不应替代脚本验证。
结构化结果 / 图结果量化比对
- 📌 Smatch: an Evaluation Metric for Semantic Feature Structures
  非常适合你引用。AMR 图评估里节点名和变量名可以不同，核心是通过图匹配计算语义三元组 F1。你的 SceneBehaviorGraph 也可以抽取模块、事件、状态、规则三元组后做 F1。
- 📌 Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task
  适合引用结构化生成结果评估。Text-to-SQL 评估不仅看字符串是否相同，还看 SQL 结构和执行结果。你的行为图也应看结构语义和执行 trace，而不是只看字段名。
- 📌 Evaluating Graph-to-Text Generation
  适合引用图结构与自然语言之间的评估问题。虽然方向相反，但它讨论了结构语义和文本语义之间的对齐。
- 📌 A Survey of Approaches to Automatic Schema Matching
  适合引用 schema matching。你的模块名、状态名、事件名不一致时，需要做字段/语义对齐，这和 schema matching 很像。
- 📌 Ontology Matching
  适合引用“把不同命名空间下的概念对齐”。你的 workpiece_pool vs remaining_parts、pallet_ready vs arrived_at_sorting_position 都属于 ontology / concept alignment 问题。
- 📌 The Hungarian Method for the Assignment Problem
  适合引用“最大权二分匹配”。你的 golden 模块和 Agent 模块数量、名称不完全一致时，可以先构造相似度矩阵，再用 Hungarian matching 找最优匹配。
- 📌 A Distance Measure Between Attributed Relational Graphs for Pattern Recognition
  适合引用 Graph Edit Distance 的早期思想。可用于说明两个行为图之间可以通过节点/边编辑代价衡量差异。
- 📌 Approximate Graph Edit Distance Computation by Means of Bipartite Graph Matching
  适合引用“用二分图匹配近似图编辑距离”。这和你想做的模块/事件/规则语义单元匹配非常接近。
流程 / Trace / 调度结果验证
- 📌 Process Mining: Data Science in Action
  适合引用流程挖掘里的 trace-based validation。你的事件链路可以看成流程模型，Agent 输出图可以通过静态 trace 检查是否覆盖 golden 流程。
- 📌 Conformance Checking Using Cost-Based Fitness Analysis
  适合引用“将实际 trace 与流程模型对齐，计算 fitness”。你的 event_bus.routes + behavior_rules + state_transition_rules 可以静态生成 trace，再与 golden trace 做 conformance checking。
- 📌 Conformance Checking: Relating Processes and Models
  适合引用流程模型一致性检查。你的行为图准确性可以表述为：预测行为图是否与标准工艺模型在关键流程上 conformance。
- 📌 Model Checking
  适合引用资源互斥、死锁、完成条件可达等性质验证。你的 resource_locks、deadlock_detection、completion_conditions 可以用 safety / liveness 思路量化。
- 📌 Principles of Model Checking
  适合引用更系统的模型检查理论。用于支撑“行为图不仅要语义相似，还要满足不变量”。
最推荐你论文里重点引用的组合
如果篇幅有限，我建议优先引用这些：
- 📌 AgentBench
  支撑 Agent 任务级量化评估。
- 📌 ToolLLM
  支撑工具/动作/参数选择类 Agent 评估。
- 📌 G-Eval
  支撑 rubric-based LLM Judge。
- 📌 BERTScore
  支撑语义相似度，不用 exact text match。
- 📌 Smatch
  支撑图结构语义匹配和 F1。
- 📌 Schema Matching Survey
  支撑事件、状态、模块字段名不同但语义对齐。
- 📌 Hungarian Method
  支撑 golden 与 prediction 单元的最大权匹配。
- 📌 Process Mining: Data Science in Action
  支撑事件链路 / trace / 工艺流程一致性验证。
- 📌 Conformance Checking
  支撑行为流程与标准模型的对齐验证。
- 📌 Principles of Model Checking
  支撑资源锁、死锁、完成条件可达等调度性质验证。




工艺仿真调度
  可以。工艺仿真调度算法建议按这几类找：离散事件仿真调度、制造系统调度、柔性作业车间调度、多机器人/AGV 调度、资源约束调度与死锁控制、仿真优化/数字孪生调度。
离散事件仿真 / 仿真调度基础
- 📌 Introduction to Discrete Event Systems
  适合引用离散事件系统 DES 的基础理论。你的 Runtime Scheduler 本质上就是基于事件触发、状态迁移和调度规则运行。
- 📌 Simulation Modeling and Analysis
  经典仿真教材，适合引用 DES、事件列表、仿真时钟、资源队列、统计评估等基础概念。
- 📌 Discrete-Event System Simulation
  适合引用仿真系统建模、事件调度、队列、资源竞争、系统性能评估。
- 📌 Simulation-based Scheduling in Manufacturing Systems: A Review
  适合引用“仿真驱动制造调度”的综述，讨论仿真如何辅助制造系统排程、调度和决策。
制造系统调度 / 作业车间调度
- 📌 Scheduling: Theory, Algorithms, and Systems
  经典调度理论书。适合引用调度问题建模、机器约束、优先级规则、启发式算法、资源约束等。
- 📌 Principles of Sequencing and Scheduling
  适合引用生产调度中的工序排序、机器分配、启发式调度规则。
- 📌 The Job-Shop Scheduling Problem: Conventional and New Solution Techniques
  适合引用作业车间调度 JSSP 的经典综述。你的机械臂、传送带、机床协同可以抽象成资源受限调度。
- 📌 A Classification Scheme for Scheduling in Flexible Manufacturing Systems
  适合引用柔性制造系统 FMS 调度分类，包括机器选择、路径选择、作业排序、动态调度。
- 📌 A Survey of Scheduling Problems with Setup Times or Costs
  如果你的后续场景涉及换型、工装、工位准备，可以引用 setup time / setup cost 调度。
- 📌 A Review of Dynamic Scheduling in Manufacturing Systems
  适合引用动态调度：设备状态变化、订单变化、阻塞、故障、实时重排。
柔性作业车间 / 资源约束调度
- 📌 A Hierarchical Approach to Solving Machine Grouping and Loading Problems of Flexible Manufacturing Systems
  适合引用 FMS 中设备分组、负载分配、资源选择问题。
- 📌 Flexible Job Shop Scheduling: A Literature Review
  适合引用柔性作业车间 FJSP。你的设备行为图里“同一任务可由不同机械臂或不同传送带执行”非常像 FJSP 的机器选择 + 工序排序问题。
- 📌 An Effective Genetic Algorithm for the Flexible Job-Shop Scheduling Problem
  适合引用启发式/遗传算法求解 FJSP，后续如果你要做优化调度可以借鉴。
- 📌 A Particle Swarm Optimization Algorithm for Flexible Job-Shop Scheduling Problem
  适合引用粒子群优化在柔性调度中的应用。
- 📌 Ant Colony Optimization for Flexible Job Shop Scheduling Problem
  适合引用蚁群优化在工艺路径/资源选择中的应用。
多机器人 / AGV / 运输调度
- 📌 Multi-Agent Path Finding: Definitions, Variants, and Benchmarks
  适合引用多机器人路径与资源冲突问题。你的多机械臂/移动设备/传送路径如果后续涉及空间冲突，可借鉴 MAPF。
- 📌 Conflict-Based Search for Optimal Multi-Agent Path Finding
  适合引用多 Agent 路径冲突解决 CBS。你的 resource_locks、互斥区域、断点占用可以借鉴它的冲突拆解思路。
- 📌 A Survey of Multi-Agent Path Finding
  适合引用 MAPF 综述，讨论多机器人路径冲突、优先级、时空资源占用。
- 📌 Integrated Scheduling of Production and Automated Guided Vehicles in Manufacturing Systems
  适合引用生产与 AGV 运输联合调度。你的传送带/搬运设备和加工设备联动很接近这个方向。
- 📌 A Review of Scheduling and Routing Algorithms for Automated Guided Vehicles
  适合引用 AGV 调度与路径规划综述。对运输、缓冲区、拥塞、资源占用很有参考价值。
阻塞、死锁、资源锁控制
- 📌 Deadlock Avoidance in Flexible Manufacturing Systems: A Petri Net Approach
  适合引用 FMS 中死锁避免。你的 resource_locks、传送带断点占用、机械臂等待都可能导致死锁。
- 📌 Deadlock Prevention Policies for Automated Manufacturing Systems Using Petri Nets
  适合引用用 Petri Net 设计死锁预防策略。
- 📌 Petri Net Synthesis for Discrete Event Control of Manufacturing Systems
  适合引用离散事件控制、制造系统 Petri Net 建模、可达性、死锁分析。
- 📌 Supervisory Control of Discrete-Event Systems
  适合引用 Ramadge-Wonham 监督控制理论。你的 SignalBusRuntime + Scheduler + Guard/Policy 可以类比成 DES supervisory control。
- 📌 On the Control of Discrete Event Systems
  经典 DES 控制论文，适合支撑“事件驱动 + guard + 控制策略”的理论基础。
仿真优化 / 数字孪生调度
- 📌 Simulation Optimization: A Review of Algorithms and Applications
  适合引用仿真优化方法，用于在仿真中比较不同调度策略、寻找最优策略。
- 📌 A Review of Optimization Algorithms for Simulation-Based Scheduling
  适合引用基于仿真的调度优化综述。
- 📌 Digital Twin-Driven Smart Manufacturing: Connotation, Reference Model, Applications and Research Issues
  适合引用数字孪生制造系统，将你的 SceneBehaviorGraph + RuntimeSnapshot 解释为数字孪生仿真运行机制。
- 📌 Digital Twin in Industry: State-of-the-Art
  适合引用工业数字孪生综述，支撑你做自然语言驱动仿真建模的背景。
- 📌 A Survey of Digital Twin in Manufacturing: Technologies, Applications and Challenges
  适合引用制造数字孪生场景中的调度、监控、预测和优化。
强化学习 / 学习型调度
- 📌 Learning to Dispatch for Job Shop Scheduling via Deep Reinforcement Learning
  适合引用 RL 学习调度规则。你后续如果把 Scheduler 从规则驱动升级成学习型策略，可以参考。
- 📌 A Review of Reinforcement Learning for Job Shop Scheduling
  适合引用 RL 在 JSSP/FJSP 中的调度应用综述。
- 📌 Learning to Schedule Job-Shop Problems: Representation and Policy Learning using Graph Neural Network and Reinforcement Learning
  适合引用 GNN + RL 对调度图建模。你的 SceneBehaviorGraph 本身就是图，非常适合后续做 GNN/RL 调度。
- 📌 Deep Reinforcement Learning for Dynamic Flexible Job Shop Scheduling
  适合引用动态柔性作业车间调度，尤其是运行中设备状态变化、任务动态到达。
最推荐你当前方案优先引用
如果你当前论文/方案重点是 SceneBehaviorGraph + Runtime Scheduler，我建议优先引用：
- 📌 Introduction to Discrete Event Systems
  支撑事件驱动仿真和 DES 理论。
- 📌 Simulation Modeling and Analysis
  支撑离散事件仿真、事件队列、资源队列。
- 📌 Scheduling: Theory, Algorithms, and Systems
  支撑调度理论、优先级规则、资源约束调度。
- 📌 Flexible Job Shop Scheduling: A Literature Review
  支撑“设备行为可选、资源动态选择”的柔性工艺调度。
- 📌 A Survey of Scheduling and Routing Algorithms for Automated Guided Vehicles
  支撑运输设备、路径、拥塞、队列、断点占用。
- 📌 Deadlock Avoidance in Flexible Manufacturing Systems: A Petri Net Approach
  支撑死锁避免、资源锁、阻塞控制。
- 📌 Supervisory Control of Discrete-Event Systems
  支撑事件、guard、policy、控制器调度。
- 📌 Simulation Optimization: A Review of Algorithms and Applications
  支撑仿真中比较和优化调度策略。
- 📌 Digital Twin-Driven Smart Manufacturing
  支撑你整体“场景建模 + 运行快照 + Runtime 执行”的数字孪生背景。
- 📌 Learning to Dispatch for Job Shop Scheduling via Deep Reinforcement Learning
  支撑后续学习型调度算法扩展。