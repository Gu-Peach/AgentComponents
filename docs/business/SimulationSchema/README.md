# 业务逻辑文档中心

> 版本：v0.1  
> 日期：2026-08-20  
> 目标：先整理系统业务概念，再进入后端与 Agent 开发。当前阶段优先定义设备数据结构。

---

## 论文研究定位

从论文视角看，当前这套 schema 体系不是单纯的软件数据结构，而是一个面向行为仿真的 **工艺行为建模框架**。

第一个研究点可以定义为：**面向 Agent 行为仿真的设备层行为建模与工艺层行为建模拆分方法**。

其中：

```text
工艺层行为建模
  先描述整个工艺场景中的物料流转、设备协作、信号依赖和运行状态结构。

设备层行为建模
  再根据行为仿真所需的信息，规范单台设备应暴露的连接接口、流程口、信号口、行为能力和运行契约。
```

也就是说，系统不是先孤立定义设备，再拼成工艺；而是先从工艺场景需要什么运行状态出发，再反推设备必须具备哪些标准化行为描述。这个顺序更适合作为“基于 Agent 的三维场景行为仿真”的研究起点。

需要特别注意：这里的设备层行为建模不只是 `physical_interfaces`。更准确地说，它是以 `Interface / Connector` 为锚点，把 `process_ports`、`signal_ports`、`transport_behaviors` 和运行契约组织成可被工艺层调用的设备行为接口模型。

这里存在两条互补的推理路径：

```text
自顶向下的 schema 规范推理：
  先判断场景级工艺仿真运行需要八大 schema 板块，
  再反推出设备层 DeviceSpec 应该如何标准化建模。

自底向上的实际 schema 推理：
  实际运行时先选用具体设备的 DeviceSpec，
  再根据工艺仿真 schema 规范编译生成场景级运行 schema。
```

前者服务论文方法论和 schema 规范设计，后者服务真实系统中的场景搭建、计划生成和 Runtime 执行。

---

## 当前文档

| 文档 | 内容 |
|---|---|
| [`device_data_structure.md`](device_data_structure.md) | 工艺行为仿真大 schema、设备层行为建模规范、八个核心板块与运行编译链路。 |
| [`common_schema_contract.json`](common_schema_contract.json) | 所有 JSON 文件共享的通用元信息规范。 |

---

## 目录结构

每个 schema 板块目录都包含三类文件：

```text
README.md    说明该环节职责、输入、输出、上游依赖和下游消费者。
schema.json  定义该环节的通用 JSON 规范。
example.json 给出该环节参与运行链路的最小示例。
```

八个目录分别对应：

| 目录 | 板块 | 作用 |
|---|---|---|
| `1.DeviceSpec` | 设备本体行为模型 | 定义设备参数、接口、信号、行为能力、运行契约和设备特殊运动特性。 |
| `2.SceneDocument` | 场景事实 | 定义设备实例、位姿、参数覆盖、流程边、物理边、信号边和物料实例。 |
| `3.SceneTransportSchema` | 场景物料流转拓扑 | 由设备本体和场景事实编译出 transport nodes、edges 和 behavior bindings。 |
| `4.SignalBusSchema` | 信号通讯契约 | 定义信号路由、等待规则、payload 和超时策略。 |
| `5.SimPlan` | Agent 仿真计划 | 定义目标、设备选择、工艺路线、transport steps、signal rules 和成功条件。 |
| `6.ExecutableSimGraph` | Runtime 可执行图 | 定义 action nodes、guards、effects、resource locks、失败处理和重规划触发。 |
| `7.RuntimeSnapshot` | 运行时状态快照 | 定义信号值、设备 FSM、物料位置、等待队列、资源锁和活动动作。 |
| `8.DeviceRuntimeProfile` | 设备当前行为画像 | 定义单设备 enabled、waiting、blocked、executing 的行为集合。 |

其中 `1.DeviceSpec` 目录采用特殊分层：外层保留通用规范、通用模板与最小示例，具体设备按 `robot_arm/`、`conveyor/`、`workpiece/` 等设备类型子目录管理。每个设备类型子目录包含 `schema.json`、`template.json` 和一个当前示例设备 JSON。

---

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

### 通用 Key 含义

| Key | 含义 |
|---|---|
| `schema_id` | 当前规范、示例或派生结构的唯一标识。 |
| `schema_type` | 当前 JSON 所属类型，例如 `DeviceSpec`、`SceneDocument`、`SimPlan`。 |
| `version` | 当前 JSON 规范或示例版本，初版统一使用 `0.1.0`。 |
| `name` | 面向人阅读的名称。 |
| `description` | 当前 JSON 的用途说明。 |
| `source` | 当前 JSON 的来源，例如人工设计、图片推断、Agent 生成或 Runtime 编译。 |
| `created_for` | 当前 JSON 服务的业务目标或研究目标。 |
| `references` | 当前 JSON 依赖、参考或引用的上游文件、图片、schema。 |
| `notes` | 设计说明、边界条件、后续注意事项。 |

### 通用嵌套 Key 含义

| Key | 含义 |
|---|---|
| `kind` | 来源类别或对象类别，例如 `manual_design`、`compiled_example`、`image_inferred`。 |
| `path` | 当前文件或来源文件路径。 |
| `compiled_from` | 派生 schema 的上游编译来源。 |
| `agent_run_id` | 生成该结构的 Agent run ID。 |
| `run_id` | 生成该结构的 Runtime run ID。 |
| `required_common_fields` | 所有 JSON 必须包含的共享字段列表。 |
| `common_field_contract` | 共享字段的字段级约束说明。 |
| `type` | 字段值类型，例如 `string`、`number`、`array`、`object`。 |
| `required` | 该字段是否必填。 |
| `example` | 字段示例值。 |
| `items` | 数组元素类型说明。 |

---

## 引用关系

实际系统运行时遵循自底向上的 schema 生成路径：

```text
DeviceSpec
  -> SceneDocument.instances 引入设备本体
  -> SceneTransportSchema / SignalBusSchema 编译场景运行结构
  -> SimPlan 表达 Agent 计划
  -> ExecutableSimGraph 落到 Runtime 可执行图
  -> RuntimeSnapshot 保存当前状态
  -> DeviceRuntimeProfile 描述设备此刻可执行行为
```

其中 `DeviceSpec` 是设备本体建模结果，不保存场景连接关系；`SceneDocument` 才保存设备实例之间的流程、物理和信号关系。

---

## 当前业务建模结论

当前系统的核心不是单个设备建模，而是面向行为仿真的 **工艺行为建模大 schema**。它由八个核心板块组成：

```text
DeviceSpec
SceneDocument
SceneTransportSchema
SignalBusSchema
SimPlan
ExecutableSimGraph / RuntimePlan
RuntimeSnapshot
DeviceRuntimeProfile
```

其中 `DeviceSpec` 由设备层行为建模提供，负责定义不同设备类型的标准化能力；其余板块围绕工艺场景、Agent 计划、Runtime 执行和实时状态展开。

原来的 `Interface / Connector`、`Signal`、`Process Flow`、`Transport / Flow` 四层不废弃，而是作为这八个板块中的基础语义：

```text
Interface / Connector  规范设备如何被连接和编排。
Signal                 规范运行时事件和值如何传递。
Process Flow           规范物料或产品按什么工艺路径流转。
Transport / Flow       规范设备如何实际执行转入、转出、等待和交接。
```

设备层行为建模需要同时满足通用性和特殊性：传送带、机械臂、仓储设备的运动特性不同，但都必须通过统一的 `physical_interfaces`、`process_ports`、`signal_ports`、`transport_behaviors` 和 `runtime_contract` 接入工艺层 schema。

---

## 与开发文档的关系

- 本目录记录业务语义和领域模型，适合先和导师/团队讨论。
- `docs/backend/` 记录后端接口、Agent Runtime、数据库方案，适合进入实现阶段。
- 如果两边冲突，以 `business/` 中的业务语义为上层依据，再更新 `docs/backend/` 的技术设计。
