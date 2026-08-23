# 后端 / Agent / 数据结构设计文档索引

> 版本：v0.1  
> 日期：2026-08-19  
> 来源：从 `docs/backend_agent_system_design.md` v0.2 拆分而来。旧总览保留为背景材料，新实现应优先阅读本目录下的拆分文档。

---

## 核心边界

本系统把“规划决策”和“实时执行”分开：

- **Agent / LangGraph** 负责理解用户目标、生成或修订结构化 artifact、处理打断、触发重规划。
- **Simulation Runtime** 负责毫秒到秒级的信号传递、设备 FSM、物料等待、资源锁和仿真事件。
- **Database / Redis** 负责保存事实、运行状态和事件流；它们不直接决定运行时因果。

这个边界避免让 LLM 管理实时信号，也避免把实时通信误降级为“Redis 里几个状态字段”。真正的实时控制在运行时调度器和设备 FSM 中完成。

---

## 文档分工

| 文档 | 负责回答的问题 | 主要读者 |
|---|---|---|
| [`backend_api_design.md`](backend_api_design.md) | 后端对外暴露哪些接口，每个接口负责什么方法和事件。 | 后端 API / 前端联调 |
| [`agent_runtime_design.md`](agent_runtime_design.md) | Agent 如何根据用户意图执行，何时触发，如何打断和恢复。 | Agent / 后端编排 |
| [`data_model_database_design.md`](data_model_database_design.md) | 事实数据如何建模、保存、恢复，Supabase/Postgres/Redis/Storage 各解决什么问题。 | 后端 / 数据库 / 仿真运行时 |

推荐阅读顺序：

1. 先读数据结构，明确 `DeviceSpec`、`SceneDocument`、三层接口和 Signal Runtime。
2. 再读后端接口，明确前端和 Agent 如何读写场景与运行仿真。
3. 最后读 Agent 设计，理解 LangGraph 节点、触发时机和 harness 约束。

---

## 当前默认假设

- 当前开发阶段只支持 GLB 资产；URDF 依赖包和复杂贴图包暂不作为第一阶段设计重点。
- 本地开发使用 Supabase local：Postgres 保存事实数据，Storage 保存 GLB/缩略图/上传文档。
- Redis 仅保存运行时状态、队列、锁、stream、仿真帧和临时状态，不作为事实库。
- 信号接口第一阶段不开放完整 UI 编辑，但必须进入后端数据模型、SimPlan 和 runtime。
- 隐式拓扑算法作为 Phase 2.5 课题内容推进；当前架构先支持显式流程连接、接口编译和基础拓扑诊断。

---

## 关键实现原则

- 场景由单个设备实例组合而成，设备实例 CRUD 是第一优先级接口。
- 连接关系分为 `process_edges`、`physical_edges`、`signal_edges`，不要再用单一 `edges` 混合表达。
- 前端可以做交互限制，但后端必须重复校验接口语义和 scene revision。
- Agent 只能生成结构化 artifact，不能直接让 LLM 写数据库。
- 普通信号传递不调用 LLM；只有死锁、超时、用户打断、计划无法继续或目标状态未达成时，runtime 才通知 Agent。

