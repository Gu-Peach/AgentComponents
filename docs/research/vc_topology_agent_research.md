# VC 4.8 工艺仿真模块调研 与 拓扑理解 Agent 设计方案

**调研对象**：Visual Components 4.8 Premium 官方帮助文档 + Python API 文档
**调研目的**：为"场景理解 → 工艺规划 → 动作执行"闭环中的第一环——拓扑理解 Agent——寻找可复刻的接口设计与实现思路
**关联文档**：`README.md`（项目总览）、`product_comparison.md`（功能对标白皮书）

---

## 一、结论摘要（先说重点）

1. **VC 4.8 自己也不做"自动拓扑理解"**。你截图里那个"工艺流动编辑器"（Unloading → ToConveyor）是**人工拖拽配置**出来的产物，VC 的 Python API 里也没有一个"给我整个车间的拓扑图"的方法。它把拓扑关系**打散存储**在每个设备的每个行为（Behaviour）的连接器（Connector）上，要拿到全局拓扑，必须自己遍历重建。这对我们是个好消息——说明"实时理解拓扑"本来就是 VC 没做到、而我们要用 LLM-Agent 做到的**颠覆点**，而不是简单复刻。
2. **VC 里有一个经常被望文生义的坑**：`vcTopology` 这个类**不是**设备拓扑，而是三维网格/NURBS 几何体的边界表示（面-边-点结构），是给 CAD 建模用的。真正对应"设备间连接关系"的是 `vcConnector` + `vcFlow` + `vcComponent`，命名上完全不含"Topology"字样，调研时容易被误导，这里先澄清。
3. **VC 的连接模型可以直接复刻为我们的 Scene Graph 数据结构**：`Component → Behaviour(Flow) → Connector[] → Connection → 另一个 Connector → 另一个 Behaviour → 另一个 Component`，这是一个标准的**端口图（Port Graph）**，我们可以原样映射到 MongoDB 的 `connections` 字段设计上，并在此基础上做 LLM 可读的图摘要。
4. **拓扑理解 Agent 不应该是单体 ReAct Agent**，而应该是 LangGraph 状态机中独立于"设备建模 Agent"（`product_comparison.md` 里已设计的 Resolver/Skill Router/Device Modeler/Guardian）的**前置感知层**，职责是把 3D 场景 + 显式连接 + 空间几何，压缩成一份 LLM 能读懂的结构化拓扑摘要，再交给调度 Agent 生成 SimPlan。这一层应该是**纯代码/图算法**，不建议用 LLM 做图遍历（不稳定、不可控），LLM 只负责在拓扑摘要基础上做语义推理。

---

## 二、VC 4.8 官方文档关键发现

### 2.1 Python API 的对象体系与命名规则

VC 4.8 Python API（[Overview](https://help.visualcomponents.com/4.8/Premium/zh-cn/Python_API/Overview2.htm)）遵循统一命名规则：常量前缀 `VC_`，事件前缀 `On`，方法首字母小写驼峰，对象前缀 `vc`，属性首字母大写。整个类体系有上百个 `vc*` 类，但和"设备互联/拓扑/工艺"直接相关的其实只有一小簇：

- **连接层**：`vcConnector`、`vcFlow`（及其子类 `vcContainer`、`vcMotionPath`、`vcTransport`、`vcRoutingRule`）
- **组件层**：`vcComponent`、`vcNode`、`vcBehaviour`
- **应用/场景层**：`vcApplication`（拿到整个 3D World 的入口）
- **工艺建模层**：`vcProcessController`、`vcProductType`、`vcRoutine`/`vcStatement` 系列（对应 product_comparison.md 中提到的 Flow → Product → Statement 三层）

### 2.2 澄清一个容易踩的坑：`vcTopology` ≠ 设备拓扑关系

调研前我们的直觉是"拓扑关系"应该对应一个叫 `vcTopology` 的类，但实际读文档后发现：**`vcTopology` 描述的是单个几何体（`vcTriangleSet`）内部的三角网格/NURBS 拓扑**——面、边、曲线环、点的邻接关系，服务于 CAD 建模（比如 `createNurbsFace`、`getFaceNormal`、`trimFace` 这些方法），和"传送带连接到升降台"这种设备级拓扑毫无关系。

这个发现对我们有实际意义：**不要在代码里把"设备拓扑"命名或类比为 VC 的 Topology 概念**，容易和未来如果要做 CAD 导入/网格处理的模块混淆命名空间。我们自己的"设备拓扑图"应该独立命名，比如 `DeviceTopologyGraph` 或 `PlantGraph`，避免语义冲突。

### 2.3 VC 中真正承载设备拓扑的对象模型

真正的设备间连接关系分布在以下几层对象上（[vcConnector](https://help.visualcomponents.com/4.8/Premium/zh-cn/Python_API/vcConnector.htm)、[vcFlow](https://help.visualcomponents.com/4.8/Premium/zh-cn/Python_API/vcFlow.htm)、[vcComponent](https://help.visualcomponents.com/4.8/Premium/zh-cn/Python_API/vcComponent.htm)、[vcApplication](https://help.visualcomponents.com/4.8/Premium/zh-cn/Python_API/vcApplication.htm)）：

| 层级 | 对象 | 关键属性/方法 | 作用 |
|---|---|---|---|
| 场景入口 | `vcApplication` | `Components`（场景内全部组件列表）、`findComponent(name)`、`connectComponents(comp1, comp2)` | 遍历全场景设备的唯一入口；`connectComponents` 会自动匹配两个组件间**所有能对上的接口**并完成物理吸附/父子挂载 |
| 组件 | `vcComponent`（继承自 `vcNode`） | `findBehaviour(name)`、`findBehavioursByType(type)`、`getTransportInfo(targetComponent)` | 一个设备实例；其"接口"以 Behaviour 的形式挂在组件树上，而不是组件本身直接暴露端口列表 |
| 行为/端口容器 | `vcFlow`（`vcBehaviour` 的子类，传送带/路径/容器等都继承它） | `Connectors`（端口列表）、`ConnectorCount`、`getConnector(index/name)`、`checkCapacity(component, index)` | 每个"能收发物料的行为"（如 OneWayPath、ComponentContainer）都有自己独立的端口列表，端口不是全局注册的，而是挂在具体行为下 |
| 端口/连接器 | `vcConnector` | `Behaviour`（属于哪个行为）、`Connection`（连接到的另一个 Connector，None 表示未连接）、`Type`（Input/Output/InputOutput）、`connect(connector)` | **这是拓扑图里真正的"边"**：一条边 = `connectorA.Connection == connectorB` |

把这四层串起来，VC 里重建一个设备的拓扑关系，本质上是这样一段可以直接类比到我们后端的伪代码：

```python
# 伪代码：在 VC 中重建全场景拓扑图（我们要做的事，VC 官方 API 本身不提供现成方法）
edges = []
for component in app.Components:                      # vcApplication.Components
    for behaviour in component.findBehavioursByType(VC_FLOW):
        for connector in behaviour.Connectors:         # vcFlow.Connectors
            if connector.Connection is not None:       # vcConnector.Connection
                target_connector = connector.Connection
                target_behaviour = target_connector.Behaviour
                target_component = target_behaviour.Component
                edges.append((component.Name, target_component.Name, connector.Type))
```

**这段代码在 VC 官方文档里并不存在**——文档只给出了两两连接一对端口的例子（`path1.getConnector('Output').connect(path2.Connectors[0])`），从未提供"生成全场景拓扑图"的封装方法。这正是我们要补的能力，也是我们能对 VC 形成差异化的地方。

### 2.4 截图与 API 共同证实的事实：VC 的拓扑是"人工声明式"的，不是"感知推断式"的

你给的截图（工艺流动编辑器：PalletGroup / PartGroup1 → Unloading → ToConveyor）展示的是 VC 的 **Process Modeling** 面板，用户需要手动为每个产品（Product）拖拽出一串流程步骤（Flow Item），这与上面 Python API 里 `vcConnector.connect()` 的物理端口连接是**两套独立的拓扑**：

- **物理拓扑**（Physical Topology）：设备与设备之间的端口连接，靠 `vcConnector`/`vcFlow`，通常在 Layout Configuration 阶段由用户拖拽吸附（`app.connectComponents`）时自动建立。
- **工艺拓扑**（Process Topology）：产品在设备间的移动路径，靠 `vcProcessController`/`vcRoutine`/`vcStatement`，需要用户在 Process Modeling 面板里手动画出 Flow → Product → Statement 三层结构（也就是截图里的 Unloading→ToConveyor）。

两者都是**声明式、非自动推断**的——VC 不会替用户"看懂"场景。这一点直接支撑了 `product_comparison.md` 里"颠覆点一：工艺建模"的判断是准确的，但也说明**我们不能简单照搬 VC 的两套拓扑模型**，而应该把这两层合并、并加上"自动感知"能力，这正是下一节要设计的拓扑理解 Agent 的核心价值。

---

## 三、可直接复刻的 VC 接口/概念清单

| VC 4.8 概念 | 对应 Python API | 复刻建议 | 落到我们平台的位置 |
|---|---|---|---|
| 全场景组件枚举 | `vcApplication.Components` | 直接对应：后端从 MongoDB `scenes` 文档里取出所有 `instance_id` | `SceneDocument.instances[]` |
| 组件按名查找 | `app.findComponent(name)` | 直接对应：`instance_id` 或用户命名的设备名索引 | 场景查询 API |
| 端口/连接器 | `vcConnector`（`Behaviour`/`Connection`/`Type`） | **重点复刻**：每个设备的每个物流接口应建模为独立的 Port 对象，而不是设备级别的一条 `connections` 记录，这样才能表达"一个传送带有入口和出口两个独立端口"这种情况 | 新增 `ports[]` 字段，见第四节数据结构设计 |
| 自动匹配连接 | `app.connectComponents(comp1, comp2)` | 部分复刻：VC 靠几何吸附+接口类型匹配自动建连接，我们可以用"空间邻近 + 端口类型互补"做同样的事，作为拓扑理解 Agent 的推断规则之一 | 第四节 4.2 隐式拓扑推断 |
| 容量测试 | `vcFlow.checkCapacity()` / `vcConnector.testCapacity()` | 复刻：调度 Agent 生成 SimPlan 前，Guardian 节点应校验目标端口/容器是否有容量，避免死锁 | Guardian Node 校验规则库 |
| 工艺流程三层结构 | `vcProcessController` → Flow → Product → Statement | 已在白皮书中复刻为 Skill 系统 + `process_config`，无需改动 | 已有设计，不重复 |
| 场景变更事件 | `OnComponentAdded` / `OnComponentRemoved` / `OnNodeConfigurationChange` | 复刻思路：Web 端场景每次拖拽/连线操作后，前端应触发对应事件推送到后端，驱动拓扑图增量更新，而不是每次全量重算 | WebSocket `scene_changed` 事件 + 拓扑增量更新 |
| 传输信息查询 | `vcComponent.getTransportInfo(target)` | 复刻：判断"当前组件能否被运输到目标组件"这一单点查询，可用于 Agent 做局部可达性校验 | Skill 校验规则的辅助方法 |

**不建议复刻的部分**：VC 的 Process Modeling 面板要求用户手动为每个 Product 逐步拖出 Flow Item（如截图所示），这是 VC "专家工具"属性的直接体现，也是我们要颠覆的对象——我们应该让 Agent 通过物理拓扑 + 自然语言意图，**自动生成**这一层，而不是提供一个更好看的手动拖拽编辑器。

---

## 四、拓扑理解 Agent 设计方案

### 4.1 为什么不能照搬 VC 的"手动连线"模式

VC 的物理拓扑虽然是自动匹配吸附（`connectComponents`），但前提是用户已经把设备**摆放到位并主动触发连接命令**。我们的场景是 Web 端用户从 eCatalog 拖入设备后，很可能只是大致摆放位置，并未显式建立任何连接——这时候如果 Agent 只读"显式 connections 字段"，会拿到一张空图，无法工作。因此拓扑理解必须做两件事，而不是一件：

1. **读取显式拓扑**：用户已经手动连过的 `connections` 记录（对应 VC 的 `vcConnector.Connection`）。
2. **推断隐式拓扑**：基于设备的空间位置、朝向、端口类型（输入/输出/物料类型）做几何邻近推断，补全用户没有手动连接、但物理上明显应该相连的部分（对应 VC `connectComponents` 的自动吸附逻辑，但我们要做得比它更智能——VC 只在用户主动拖拽吸附时触发，我们要能在任意时刻主动"看懂"整个车间）。

### 4.2 两层拓扑数据结构设计

在现有 `SceneDocument`（MongoDB）基础上，建议把设备的"接口"从当前的粗粒度 `connections` 记录，细化为独立的 Port 级对象，直接对应 VC 的 `vcConnector`：

```json
{
  "instance_id": "conveyor_1",
  "device_type": "conveyor",
  "pose": { "position": [x, y, z], "rotation": [rx, ry, rz] },
  "ports": [
    {
      "port_id": "conveyor_1.entry",
      "type": "input",
      "local_offset": [0, 0, 0],
      "product_types": ["pallet", "box"],
      "connection": null
    },
    {
      "port_id": "conveyor_1.exit",
      "type": "output",
      "local_offset": [2.4, 0, 0],
      "product_types": ["pallet", "box"],
      "connection": "storage_01.cell_A2"
    }
  ]
}
```

- `connection` 非空 → 显式拓扑边（用户手动连接或场景加载时已固化）。
- `connection` 为空 → 交给拓扑理解 Agent 做隐式推断候选。

### 4.3 拓扑构建算法（Perception 阶段，纯代码，不调用 LLM）

```
输入：SceneDocument.instances[]（含每个实例的 pose 与 ports[]）

第一步 · 显式边收集
  for instance in instances:
    for port in instance.ports:
      if port.connection is not None:
        edges.add(Edge(port, resolve(port.connection), kind="explicit"))

第二步 · 隐式边推断（几何 + 语义双重过滤）
  for portA in unconnected_output_ports:
    candidates = spatial_index.query_nearby(portA.world_position, radius=R)
    for portB in candidates:
      if portB.type in (input, input_output)
         and portB.product_types ∩ portA.product_types != ∅
         and distance(portA, portB) < threshold
         and orientation_compatible(portA, portB):
        edges.add(Edge(portA, portB, kind="inferred", confidence=score))

第三步 · 图组装
  graph = build_directed_graph(instances, edges)
  返回：
    - 强连通/弱连通分量（识别出几条独立产线）
    - 每个设备的入度/出度（识别孤立设备、悬空端口）
    - 拓扑排序（识别物料流的上下游顺序，供调度 Agent 使用）
```

第二步的"隐式边推断"就是我们对 VC `connectComponents` 的**升级复刻**：VC 只在用户主动拖拽发出吸附命令时才触发匹配，我们把它做成场景加载/变更时可随时重跑的后台图算法，并且加入置信度分数——置信度低于阈值的候选边不自动写入 `connections`，而是作为"建议连接"提示给用户或作为 Agent 追问的依据（对应白皮书里 Level 4/5 的 Human-in-the-loop 机制）。

**这一步坚决不用 LLM 做**。图遍历、空间邻近查询、拓扑排序都是成熟的确定性算法（可以用 `networkx` 直接实现弱连通分量、拓扑排序），LLM 处理这类结构化图运算既不稳定也没必要，容易产生幻觉边或漏边。LLM 的价值应该留到下一层——基于这份**已经算好的拓扑摘要**做语义层面的推理。

### 4.4 拓扑摘要转 LLM 可读格式

图算法的输出对 LLM 不友好（邻接表、坐标数值），需要转成一份精简的自然语言/结构化摘要再喂给 Agent，例如：

```
产线 1（3 台设备，物料类型：pallet）：
  conveyor_1 --[exit→entry, 置信度: 显式]--> storage_01
  storage_01 --[cell_A2→base, 置信度: 0.86 推断]--> lift_2
悬空端口：lift_2.output（未连接任何设备，可能是产线终点或缺失设备）
```

这份摘要既可以作为调度 Agent（白皮书中 Level 1"极简指令"场景）读取 workflow 和 topology 的数据源，也可以在用户输入模糊指令时，作为 Resolver Node 判断"用户说的'升降台'具体指哪个 instance_id"的上下文依据。

---

## 五、Agent 范式与框架选型

### 5.1 结论：LangGraph 图状态机，而非单体 ReAct Agent

`product_comparison.md` 中已经为"设备建模"确定了 LangGraph 状态机范式（Resolver → Skill Router → Device Modeler → Guardian → Scene Patcher），这个选择应该延续到拓扑理解层，理由：

- **拓扑理解和设备建模是两类不同的任务**：前者是"感知 + 图计算"，输出是结构化的场景摘要；后者是"意图理解 + 结构化生成"，输出是单设备的 `process_config`。把两者塞进同一个 ReAct 循环里让 LLM 自由决定调用顺序，会导致 LLM 在该跑图算法的时候去"猜"拓扑关系，产生幻觉。
- **LangGraph 的显式状态机**天然适合把"确定性代码步骤"（图算法）和"LLM 推理步骤"（语义解释、意图澄清）分开成不同节点，通过状态在节点间传递，比单体 Agent 自主决策更可控、更可调试——这对工业仿真场景尤其重要，因为拓扑算错会导致整条产线仿真逻辑错误。
- 团队已经在用 LangGraph 做设备建模，拓扑理解 Agent 复用同一套框架、同一个 `MemorySaver`/状态管理机制，减少额外的技术栈开销。

### 5.2 拓扑理解 Agent 在整体工作流中的位置

建议在现有 Resolver Node **之前**插入一个独立的感知子图（Perception Subgraph），作为所有用户请求的公共前置步骤，而不是每次都重新触发：

```
场景变更事件（WebSocket: device_added / device_moved / port_connected）
    │
    ▼
Topology Builder Node（纯代码，第 4.3 节算法）
    产出：DeviceTopologyGraph（存入 Redis，key: topology:{project_id}）
    │
    ▼
Topology Summarizer Node（轻量 LLM 调用，或纯模板拼接）
    产出：面向 LLM 的自然语言拓扑摘要（第 4.4 节格式）
    │
    ▼
（缓存至此为止，不等用户提问；用户提问时直接读取缓存的摘要）
    │
用户输入「让升降台把物料送到 A2 格位」
    │
    ▼
Resolver Node（复用白皮书已有设计）
    现在多了一份"拓扑摘要"作为上下文，可以准确判断"升降台"指代哪个 instance_id，
    以及 A2 格位与该升降台是否物理可达（读 DeviceTopologyGraph 校验）
    │
    ▼
Skill Router → Device Modeler → Guardian → Scene Patcher（白皮书已有设计，不变）
```

关键设计原则：**拓扑图的构建与用户的自然语言请求解耦**。拓扑图应该随场景变更事件增量更新并常驻缓存，而不是每次用户提问才现算——这样才能支撑白皮书 Level 1"极简指令"场景里"Agent 自动读取 scene.json 的 topology"的假设成立，否则每次对话都要重新跑一遍图算法，延迟不可控。

### 5.3 节点职责细分

| 节点 | 类型 | 输入 | 输出 | 是否用 LLM |
|---|---|---|---|---|
| Topology Builder | 代码节点 | SceneDocument | DeviceTopologyGraph（邻接表 + 分量 + 拓扑序） | 否，用 `networkx` |
| Consistency Checker | 代码节点 | DeviceTopologyGraph | 异常列表（悬空端口、环路、类型不匹配的连接） | 否 |
| Topology Summarizer | 模板/轻量 LLM | DeviceTopologyGraph + 异常列表 | 自然语言摘要 | 可选（模板拼接优先，复杂场景可用小模型做归纳） |
| Resolver（已有） | LLM | 用户输入 + 拓扑摘要 | 结构化意图 | 是 |

Consistency Checker 这一节点是对 VC 的**再升级**：VC 本身不会主动提示"这个端口没连东西可能有问题"，用户得自己在 3D 视口里排查；我们可以把悬空端口、环路（物料死循环）、端口类型不匹配这些问题在场景变更后立刻检测出来，作为终端面板日志（对应白皮书"输出终端"里 Agent 调度日志的一种）主动提示用户，这是比 VC 更好用的地方，也值得写进后续版本的颠覆点里。

### 5.4 与 SimPlan / Skill 系统的衔接

DeviceTopologyGraph 是 Skill 系统里 `LiftSkill.build_prompt()` 这类方法的重要输入源之一：目前白皮书中的例子（"将传送带出口的物料送到仓储柜 A2 格位"）里，"conveyor_1.exit"和"A2 格位"这两个引用能否成立，本质上就是在查 DeviceTopologyGraph 里是否存在这条边或可达路径。建议 Guardian Node 的业务规则校验中新增一类校验：**拓扑可达性校验**（目标设备/格位是否与源设备存在有效路径），与已有的参数范围校验（如速度是否在合法区间）并列。

---

## 六、参考资料

- [VC 4.8 Python API Overview](https://help.visualcomponents.com/4.8/Premium/zh-cn/Python_API/Overview2.htm)
- [vcConnector](https://help.visualcomponents.com/4.8/Premium/zh-cn/Python_API/vcConnector.htm)
- [vcFlow](https://help.visualcomponents.com/4.8/Premium/zh-cn/Python_API/vcFlow.htm)
- [vcComponent](https://help.visualcomponents.com/4.8/Premium/zh-cn/Python_API/vcComponent.htm)
- [vcBehaviour](https://help.visualcomponents.com/4.8/Premium/zh-cn/Python_API/vcBehaviour.htm)
- [vcApplication](https://help.visualcomponents.com/4.8/Premium/zh-cn/Python_API/vcApplication.htm)
- [vcTopology](https://help.visualcomponents.com/4.8/Premium/zh-cn/Python_API/vcTopology.htm)（用于澄清该概念与设备拓扑无关）
- Visual Components Academy：Connect Interfaces 课程（物理接口连接的用户侧操作说明）
- Visual Components 官方社区论坛：`app.connectComponents()` / `node.attach()` 相关讨论帖，佐证物理连接是主动触发而非自动感知

---

## 附：后续可推进的下一步

1. 在现有 `system_directory_structure.md` 的后端目录里，确定 Topology Builder / Consistency Checker 的代码落点（建议作为独立的 `topology` 模块，与 `agent` 模块并列，被 Resolver Node 依赖而非包含在内）。
2. 明确"隐式拓扑推断"的置信度阈值与用户确认交互——这部分建议放进 AI 设计文档（`ai_simulation_agent_design.md`）里细化 Human-in-the-loop 的触发条件。
3. 补充空间邻近推断的具体算法参数（半径 R、朝向容差角度等），这部分依赖具体设备库的尺寸分布，建议用少量真实车间布局样本做经验取值，而不是纯理论设定。
