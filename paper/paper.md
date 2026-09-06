## 近十年论文引用清单

筛选口径：保留 2017-2026 年的论文、会议论文、期刊论文和综述论文；删除书籍、教材、专著、章节，以及 2017 年以前的经典论文。以下条目均适合继续放在论文引用或相关工作中。

## LLM & Agent 量化评估

### LLM Agent 量化评估

- 📌 [AgentBench: Evaluating LLMs as Agents](https://arxiv.org/abs/2308.03688)（2023）
  适合引用“Agent 能力可拆成多任务环境，用任务成功率、完成率、交互轮次、效率等指标量化”。你的 Agent 不是只生成文本，而是完成一个场景建模任务，可以借鉴它的 benchmark 设计。
- 📌 [WebArena: A Realistic Web Environment for Building Autonomous Agents](https://arxiv.org/abs/2307.13854)（2023）
  适合引用“在真实环境中评估 Agent 的任务完成率”。虽然它是 Web Agent，但思路类似：给定任务目标，看 Agent 是否生成能完成任务的操作链路。
- 📌 [Mind2Web: Towards a Generalist Agent for the Web](https://arxiv.org/abs/2306.06070)（2023）
  适合引用“把 Agent 行为拆成 action selection、element selection、operation prediction 等可量化子任务”。你的场景里也可以拆成模块选择、事件选择、状态变量选择、行为规则选择。
- 📌 [ToolLLM: Facilitating Large Language Models to Master 16000+ Real-world APIs](https://arxiv.org/abs/2307.16789)（2023）
  适合引用工具调用型 Agent 的评估方式：tool selection、参数生成、任务完成率。你的 Agent 也需要选择设备行为、策略函数和事件路由，可以借鉴它的分项指标。
- 📌 [SWE-bench: Can Language Models Resolve Real-World GitHub Issues?](https://arxiv.org/abs/2310.06770)（2023）
  适合引用“用真实任务 + 可执行测试判断结果是否正确”。你的 SceneBehaviorGraph 也可以通过 schema 校验、语义断言、trace 校验来判断是否通过。
- 📌 [GAIA: A Benchmark for General AI Assistants](https://arxiv.org/abs/2311.12983)（2023）
  适合引用通用 Agent 的多步推理、工具使用、真实任务完成率。你的 Agent 也属于多步结构化任务：理解场景、规划行为、生成图、校验图。
- 📌 [OSWorld: Benchmarking Multimodal Agents for Open-Ended Tasks in Real Computer Environments](https://arxiv.org/abs/2404.07972)（2024）
  适合引用“多模态 Agent 在真实环境中的任务成功率、步骤效率、操作正确性”。你这里也有场景图片参与理解，可以借鉴它的多模态 Agent 评估思路。
- 📌 [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)（2022）
  适合引用 Agent 推理-行动循环的思想。虽然不是专门评估论文，但可用于说明 Agent 任务需要分步骤 reasoning，并对每步结果做验证。

### LLM 生成结果量化评估

- 📌 [BERTScore: Evaluating Text Generation with BERT](https://arxiv.org/abs/1904.09675)（2019）
  适合引用“用 contextual embedding 做语义相似度，而不是只看字符或词重叠”。你的模块描述、规则描述、目标覆盖度可以借鉴 BERTScore 思路。
- 📌 [BLEURT: Learning Robust Metrics for Text Generation](https://arxiv.org/abs/2004.04696)（2020）
  适合引用“学习式评估指标，比传统 overlap 更接近人工判断”。如果你后续想训练或微调一个评估器，可以借鉴。
- 📌 [MoverScore: Text Generation Evaluating with Contextualized Embeddings and Earth Mover Distance](https://arxiv.org/abs/1909.02622)（2019）
  适合引用“用语义 token 分布距离评估生成文本”。可作为你做模块/事件描述语义距离的参考。
- 📌 [BARTScore: Evaluating Generated Text as Text Generation](https://arxiv.org/abs/2106.11520)（2021）
  适合引用“用预训练生成模型计算候选文本与参考文本之间的生成概率”。可作为语义相似度评估的另一类参考。
- 📌 [G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment](https://arxiv.org/abs/2303.16634)（2023）
  适合引用 LLM-as-a-Judge 和 rubric-based evaluation。你的行为规则、策略语义、目标覆盖度可以用 rubric 让 LLM 辅助评分。
- 📌 [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685)（2023）
  适合引用“LLM 可以作为评估器，但需要控制偏差和一致性”。你的方案里 LLM Judge 应作为补充，不应替代脚本验证。

### 结构化结果 / 图结果量化比对

- 📌 [Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task](https://arxiv.org/abs/1809.08887)（2018）
  适合引用结构化生成结果评估。Text-to-SQL 评估不仅看字符串是否相同，还看 SQL 结构和执行结果。你的行为图也应看结构语义和执行 trace，而不是只看字段名。
- 📌 [Evaluating Generative Models for Graph-to-Text Generation](https://arxiv.org/abs/2307.14712)（2023）
  适合引用图结构与自然语言之间的评估问题。虽然方向相反，但它讨论了结构语义和文本语义之间的对齐。

### 推荐优先引用组合

- 📌 [AgentBench](https://arxiv.org/abs/2308.03688)（2023）
  支撑 Agent 任务级量化评估。
- 📌 [ToolLLM](https://arxiv.org/abs/2307.16789)（2023）
  支撑工具/动作/参数选择类 Agent 评估。
- 📌 [G-Eval](https://arxiv.org/abs/2303.16634)（2023）
  支撑 rubric-based LLM Judge。
- 📌 [BERTScore](https://arxiv.org/abs/1904.09675)（2019）
  支撑语义相似度，不用 exact text match。
- 📌 [Spider](https://arxiv.org/abs/1809.08887)（2018）
  支撑结构化生成结果的结构与执行结果评估。
- 📌 [Evaluating Generative Models for Graph-to-Text Generation](https://arxiv.org/abs/2307.14712)（2023）
  支撑图结构与文本语义之间的对齐评估。

## 工艺仿真调度

可以。工艺仿真调度算法建议按这几类找：制造系统调度、柔性作业车间调度、多机器人/AGV 调度、仿真优化、数字孪生调度、强化学习调度。

### 柔性作业车间 / 资源约束调度

- 📌 [The Flexible Job Shop Scheduling Problem: A Review](https://doi.org/10.1016/j.ejor.2023.05.017)（2024）
  适合引用柔性作业车间 FJSP。你的设备行为图里“同一任务可由不同机械臂或不同传送带执行”非常像 FJSP 的机器选择 + 工序排序问题。

### 多机器人 / AGV / 运输调度

- 📌 [Multi-Agent Pathfinding: Definitions, Variants, and Benchmarks](https://arxiv.org/abs/1906.08291)（2019）
  适合引用多机器人路径与资源冲突问题。你的多机械臂、移动设备、传送路径如果后续涉及空间冲突，可借鉴 MAPF。

### 仿真优化 / 数字孪生调度

- 📌 [Digital Twin-Driven Smart Manufacturing: Connotation, Reference Model, Applications and Research Issues](https://doi.org/10.1016/j.rcim.2019.101837)（2020）
  适合引用数字孪生制造系统，将你的 SceneBehaviorGraph + RuntimeSnapshot 解释为数字孪生仿真运行机制。
- 📌 [Digital Twin in Industry: State-of-the-Art](https://doi.org/10.1109/TII.2018.2873186)（2019）
  适合引用工业数字孪生综述，支撑你做自然语言驱动仿真建模的背景。

### 强化学习 / 学习型调度

- 📌 [Learning to Dispatch for Job Shop Scheduling via Deep Reinforcement Learning](https://arxiv.org/abs/2010.12367)（2020）
  适合引用 RL 学习调度规则。你后续如果把 Scheduler 从规则驱动升级成学习型策略，可以参考。
- 📌 [A Literature Review of Reinforcement Learning Methods Applied to Job-Shop Scheduling Problems](https://doi.org/10.1016/j.cor.2024.106929)（2024）
  适合引用 RL 在 JSSP/FJSP 中的调度应用综述。
- 📌 [Learning to Schedule Job-Shop Problems: Representation and Policy Learning using Graph Neural Network and Reinforcement Learning](https://arxiv.org/abs/2106.01086)（2021）
  适合引用 GNN + RL 对调度图建模。你的 SceneBehaviorGraph 本身就是图，非常适合后续做 GNN/RL 调度。
- 📌 [Deep Reinforcement Learning for Dynamic Flexible Job Shop Scheduling with Random Job Arrival](https://doi.org/10.3390/pr10040760)（2022）
  适合引用动态柔性作业车间调度，尤其是运行中设备状态变化、任务动态到达。

### 推荐优先引用组合

- 📌 [The Flexible Job Shop Scheduling Problem: A Review](https://doi.org/10.1016/j.ejor.2023.05.017)（2024）
  支撑“设备行为可选、资源动态选择”的柔性工艺调度。
- 📌 [Multi-Agent Pathfinding: Definitions, Variants, and Benchmarks](https://arxiv.org/abs/1906.08291)（2019）
  支撑多设备路径规划、冲突检测和资源占用。
- 📌 [Digital Twin-Driven Smart Manufacturing](https://doi.org/10.1016/j.rcim.2019.101837)（2020）
  支撑整体“场景建模 + 运行快照 + Runtime 执行”的数字孪生背景。
- 📌 [Learning to Dispatch for Job Shop Scheduling via Deep Reinforcement Learning](https://arxiv.org/abs/2010.12367)（2020）
  支撑后续学习型调度算法扩展。
- 📌 [A Literature Review of Reinforcement Learning Methods Applied to Job-Shop Scheduling Problems](https://doi.org/10.1016/j.cor.2024.106929)（2024）
  支撑学习型调度方法的近期综述。
