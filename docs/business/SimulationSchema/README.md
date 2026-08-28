# 业务逻辑文档中心

> 版本：v0.2
> 日期：2026-08-26
> 目标：以 `SceneBehaviorGraph` 作为 Agent 行为建模的基线产物，收敛早期过细的中间 schema。

---

## 论文研究定位

当前 schema 体系用于描述基于 Agent 的三维工业场景行为仿真。它不是单纯保存前端场景，而是让 Agent 和 Runtime 能理解：场景中有哪些设备、设备如何连接、用户希望场景如何运行、运行过程中信号和状态如何驱动设备行为。

新的基线结论是：**场景行为建模结果应该是描述真实运作方式的 `SceneBehaviorGraph`，而不是一组彼此割裂的约束型中间产物。**

因此，当前基线拆成两层：

```text
设备层行为建模
  DeviceSpec 定义单台设备原生能力：接口、信号口、行为能力、运行契约和特殊运动/容量约束。

场景层行为建模
  SceneDocument 定义场景事实；SceneBehaviorGraph 定义该场景在用户目标下如何通过事件、状态、策略和行为规则运行。
```

---

## 当前文档

| 文档 | 内容 |
|---|---|
| [`device_data_structure.md`](device_data_structure.md) | 当前 v0.2 基线：`DeviceSpec + SceneDocument -> SceneBehaviorGraph -> RuntimeSnapshot`。 |
| [`../../design/agent_scene_behavior_graph_design.md`](../../design/agent_scene_behavior_graph_design.md) | Agent 生成 `SceneBehaviorGraph` 的技术方案、Runtime 调度方案、存储方案和学术创新点。 |
| [`common_schema_contract.json`](common_schema_contract.json) | 所有 JSON 文件共享的通用元信息规范。 |
| [`4.SceneBehaviorGraph/`](4.SceneBehaviorGraph/) | Agent 生成的场景行为图规范与示例。 |
| [`demo/pallet_sorting_line/`](demo/pallet_sorting_line/) | 基于 `docs/business/test/1.png` 的托盘分拣线 demo，展示共享工件池、backpressure 与事件驱动运行。 |

---

## 当前基线目录结构

| 目录 | 板块 | 状态 | 作用 |
|---|---|---|---|
| `1.DeviceSpec` | 设备本体行为模型 | 当前基线 | 定义设备原生能力。 |
| `2.SceneDocument` | 场景事实 | 当前基线 | 定义设备实例、位姿、物料和显式连接。 |
| `3.RuntimeSnapshot` | 运行时状态快照 | 当前基线 | Runtime 保存高频实时状态事实。 |
| `4.SceneBehaviorGraph` | 场景行为图 | 当前基线 | Agent 基于用户目标生成的场景实际运作方式。 |

## JSON 通用规范

所有 JSON 文件都应包含以下共享字段：

```text
schema_id
schema_type
version
name
description
source
created_for
references
notes
```

共享字段的语义以 `common_schema_contract.json` 为准。当前阶段这些 JSON 是可读规范与示例，不是严格 JSON Schema Draft；后续可转换为 Zod 或标准 JSON Schema。

---

## 当前引用关系

```text
DeviceSpec
  -> SceneDocument.instances[].spec_id 引用设备能力

SceneDocument
  -> 保存场景事实、物料和显式 process / physical / signal 连接

Agent(DeviceSpec + SceneDocument + 用户目标)
  -> SceneBehaviorGraph

Runtime(SceneBehaviorGraph)
  -> 初始化 RuntimeSnapshot

Runtime loop(SceneBehaviorGraph + RuntimeSnapshot)
  -> Scheduler 选择行为
  -> ActionExecutor 执行动作
  -> SignalBusRuntime 按 event_bus 投递事件
  -> SnapshotManager 更新 RuntimeSnapshot
```

其中：

```text
SceneBehaviorGraph 是持久化的场景行为建模结果；
RuntimeSnapshot 是运行时状态事实，不负责表达行为模型；
SignalBusRuntime 是 Runtime 内部模块，不是独立 schema。
```

---

## 当前业务建模结论

当前系统的核心不是单个设备建模，也不是把计划拆成多个中间约束，而是面向行为仿真的 **场景行为图建模**。

```text
DeviceSpec
SceneDocument
SceneBehaviorGraph
RuntimeSnapshot
```

其中：

- `DeviceSpec` 定义设备原生能力，不保存场景连接关系。
- `SceneDocument` 定义场景事实，不保存运行状态。
- `SceneBehaviorGraph` 定义该场景在用户目标下的实际运行方式，包括模块、事件总线、状态变量、行为规则、状态迁移、策略函数和结束条件。
- `RuntimeSnapshot` 保存运行中的实时状态值，包括信号值、设备状态、物料位置、队列、资源锁、负载和 active actions。

---

## 与开发文档的关系

- 本目录记录业务语义和领域模型，适合先和导师/团队讨论。
- `docs/backend/` 记录后端接口、Agent Runtime、数据库方案，进入实现阶段时需要同步更新。
- 如果两边冲突，以 `business/` 中的当前 v0.2 基线为上层依据，再更新 `docs/backend/` 的技术设计。
