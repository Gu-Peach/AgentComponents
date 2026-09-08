# SceneDocument / TopologyGraph / SceneBehaviorGraph / DeviceSpec 执行链路总结

本文记录当前产线仿真运行链路的分层关系，重点解释 `SceneDocument`、`TopologyGraph`、`SceneBehaviorGraph`、`SignalBusRuntime`、`DeviceSpec` 和前端执行器之间的职责边界。

## 1. 当前主链路

当前已实现的主链路更接近 Phase 1.5 / Phase 2 的基础闭环：

```text
SceneDocument
  -> TopologyGraph
  -> SignalBusRuntime
  -> DeviceRuntime / RuntimeHandlerRegistry
  -> DeviceSpec.transport_behaviors
  -> device_task / device_behavior_triggered
  -> 前端行为执行器播放动画
  -> 前端 action complete 回调后端
```

更具体地说：

1. `SceneDocument` 定义场景事实。
2. `TopologyGraph` 从 `SceneDocument` 派生拓扑索引。
3. `SignalBusRuntime` 根据 `TopologyGraph.signal_graph` 或 `SceneDocument.signal_edges[]` 投递信号。
4. `DeviceRuntime` 根据目标信号解析目标设备和信号端口。
5. `RuntimeHandlerRegistry` 根据 `device_type + signal_port` 查找应触发的 `behavior_id`。
6. `DeviceSpec.transport_behaviors[]` 提供设备支持哪些行为，以及哪些输入信号能触发这些行为。
7. 后端生成 `device_task` 和 `device_behavior_triggered` 前端事件。
8. 前端收到事件后执行 `play(instance_id, behavior_id, payload)`。
9. 前端行为完成后，通过 action complete 接口通知后端。

## 2. 各层职责

### 2.1 SceneDocument

`SceneDocument` 是场景事实源，负责描述“这个场景里有什么、怎么连”。

它主要保存：

- `instances[]`：场景中的设备实例，例如 `main_conveyor_1`、`robot_1`。
- `materials[]`：场景中的物料实例，例如 `part_001`。
- `process_edges[]`：工艺/物料流关系，例如 conveyor 输出到 robot 输入。
- `physical_edges[]`：设备物理连接/装配关系，例如底部包围框安装点、底座连接点、夹具安装点之间的连接；不表达物料运输路径。
- `signal_edges[]`：信号端口之间的静态连接关系。
- `instances[].param_overrides`：实例级参数覆盖。
- `instances[].runtime_geometry`：场景级执行几何，例如传送带实例的 `transport_path`、`waypoints`、`stop_points`，以及机械臂实例的 `process_points`、`pick_place_path`。这些执行几何应从工艺接口/process point 派生，而不是从 physical interface 派生。
- `instances[].runtime_kinematics`：场景实例级运动结构，例如机械臂由 `DeviceSpec.type_specific_contract.urdf` 和 GLB 节点绑定编译出的 IK chain、joint nodeName、TCP。

关键点：`SceneDocument` 不是运行时状态表。它不保存设备当前是否 busy，也不保存当前 action 进度。这些属于 RuntimeSnapshot / RuntimeStateStore。

### 2.2 TopologyGraph

`TopologyGraph` 是从 `SceneDocument` 编译出来的运行索引，不是新的事实源。

它用于把场景连接关系整理成更适合运行时查询的图结构：

- `physical_graph`：物理接口图。
- `process_graph`：工艺流图。
- `signal_graph`：信号投递图。
- `transport_graph`：运输可达性图。

当前 `SignalBusRuntime` 的信号路由优先读取当前 revision 匹配的 `TopologyGraph.signal_graph.edges[]`。如果没有可用 topology，或者 topology 的 scene revision 与 run 的 base scene revision 不一致，则回退读取 `SceneDocument.signal_edges[]`。

### 2.3 SceneBehaviorGraph

`SceneBehaviorGraph` 是更高层的行为规则图，用于描述“场景应该如何运行”。

它适合管理：

- 事件定义。
- rule / guard 前置条件。
- policy 策略函数。
- resource lock。
- backpressure。
- workpiece claim。
- FSM 状态流转。
- 完成条件和失败观测。

但当前主 API 运行链路还没有完整依赖 `SceneBehaviorGraph` 驱动。也就是说，当前不是先由 `SceneBehaviorGraph` 做完整规则调度，再触发所有设备动作；当前先跑通的是信号路由到设备任务的基础闭环。

因此现阶段可以理解为：

```text
当前：SceneDocument.signal_edges / TopologyGraph.signal_graph -> SignalBusRuntime -> device task
目标：SceneDocument + TopologyGraph + SceneBehaviorGraph -> Scheduler / Rule Runtime -> device task
```

### 2.4 SignalBusRuntime

`SignalBusRuntime` 负责信号事件投递。

核心流程：

```text
emit(source_signal, value, payload)
  -> 记录 source signal latest value
  -> 查 signal_graph 或 SceneDocument.signal_edges[]
  -> 匹配 source == 当前 signal 的 enabled edge
  -> 判断 trigger，例如 on_rising_edge / on_change / level
  -> 执行 transform，当前主要支持 identity
  -> 写入 target signal latest value
  -> 写入 routed_signal_event
  -> 调 DeviceRuntime.on_signal(target_signal)
  -> 生成 device_task
  -> 发布 device_behavior_triggered 给前端
```

这里的 signal 不是直接绑定一段任意回调函数。更准确的模型是：

```text
target signal port
  -> 解析目标设备实例
  -> 读取目标实例 spec_id
  -> 查 DeviceSpec.signal_ports / interface_bindings / transport_behaviors
  -> 解析出 behavior_id
```

例如：

```text
main_conveyor_2.part_ready
  -> robot_1.start_pick
  -> robot_1 引用 robot_arm_1
  -> robot_arm_1.transport_behaviors[] 中 start_pick 触发 pick_and_place
  -> 生成 robot_1.pick_and_place 任务
```

### 2.5 DeviceSpec

`DeviceSpec` 是设备“类”的能力定义，描述这个设备本体能做什么。

它保存：

- `physical_interfaces[]`：设备物理连接锚点，例如模型包围框底部四点、底座安装点、夹具安装点；只回答设备/模型之间如何连接或吸附。
- `process_ports[]`：工艺流和物料运动端口，例如 conveyor 的 `flow_input` / `flow_output`、robot 的 pick/place process point；它们可以有具体坐标，并作为物料吸附、运输、抓取、放置的执行点。
- `signal_ports[]`：信号端口，例如 `part_ready`、`start_pick`、`pause_pick`。
- `interface_bindings[]`：物理接口、工艺端口、信号端口、行为之间的绑定关系。
- `transport_behaviors[]`：设备支持的行为，例如 `transport_to_exit`、`pick_and_place`。
- `params_schema`：设备默认参数 schema。
- `type_specific_contract`：设备类型专有能力，例如 conveyor stop point model、robot urdf joints。

执行时，DeviceSpec 主要回答两个问题：

1. 某个输入信号能不能触发这个设备。
2. 触发后应该执行哪个 `behavior_id`。

## 3. 执行参数优先级

真正执行行为时，运行时基础参数来自 `SceneDocument.instances[]`；`Runtime event payload` 只作为本次动作的临时覆盖或物料选择信息。更合理的优先级是：

```text
Runtime event payload
  > SceneDocument.instances[].runtime_geometry
  > SceneDocument.instances[].runtime_kinematics
  > SceneDocument.instances[].param_overrides
  > DeviceSpec.params_schema.default / type_specific_contract
```

含义：

- `Runtime event payload`：本次动作特定参数或覆盖，例如 `material_id`、`target_conveyor_id`、临时 `waypoints`。
- `SceneDocument.runtime_geometry`：场景实例级执行几何，例如某条传送带在当前场景中的起点、终点和停留点，或某个机械臂的 pick/place 点和抓放路径。
- `SceneDocument.param_overrides`：场景实例级参数，例如速度、容量、停留点数量。
- `SceneDocument.runtime_kinematics`：场景实例级 IK/运动结构快照，例如机械臂 joint chain、joint nodeName、TCP；由 DeviceSpec 的局部默认定义编译而来。
- `DeviceSpec`：设备类默认能力、局部工艺点和默认运动结构，主要作为编译来源；运行时播放动画不应重新依赖它推断场景坐标。

以传送带为例：

```text
DeviceSpec.conveyor_1
  -> physical_interfaces 定义设备模型连接锚点，例如底部包围框四点
  -> process_ports 定义 flow_input / flow_output 的局部工艺坐标
  -> 定义 transport_to_exit 行为
  -> 定义默认 stop_point_model，并从 flow_input / flow_output 生成停留点

SceneDocument.main_conveyor_1
  -> 引用 conveyor_1
  -> 覆盖 speed_mps / capacity / stop_point_count
  -> 提供当前场景下的 runtime_geometry.transport_path

Runtime event
  -> 指定 carrier_id 或 material_id
  -> 可选指定本次动作 waypoints
```

如果 payload 没有显式 `waypoints`，执行器应优先读 `SceneDocument.instances[].runtime_geometry`：传送带读 `transport_path`，机械臂读 `pick_place_path`。如果 scene 也没有给，才在编译/校准阶段用 `DeviceSpec.process_ports.flow_input/flow_output + instance.transform` 推导并写回 SceneDocument。`physical_interfaces` 不应作为物料路径 fallback，除非某个设备明确把物理连接点同时声明为工艺点。

## 4. 前后端分工

当前项目是前后端分离，所以 VC 中可能集中在组件脚本里的行为执行逻辑，被拆成了两部分：

- 后端负责信号投递、状态记录、任务生成、行为事件发布。
- 前端负责根据 `behavior_id + payload` 播放动画。

后端不会直接移动 Three.js 场景里的模型。后端发布的是：

```text
device_behavior_triggered
```

前端收到后执行：

```text
play(instance_id, behavior_id, payload)
```

行为完成后，前端再回调后端：

```text
POST action complete
```

后端收到完成事件后，再推进状态更新和下一轮信号触发。

## 5. 当前链路和目标链路的区别

当前版本优先跑通最小闭环：

```text
信号发出
  -> 信号路由
  -> 目标设备任务
  -> 前端行为播放
  -> 行为完成回调
```

后续增强版本再把复杂调度补进去：

- `SceneBehaviorGraph` 规则运行时。
- guard 前置条件判断。
- policy 策略函数执行。
- resource lock。
- FSM 状态机。
- backpressure 完整调度。
- 编译后的 `TopologyGraph` + `SceneBehaviorGraph` 联合运行。

因此当前可以接受的工程判断是：先让 `SceneDocument + TopologyGraph.signal_graph + SignalBusRuntime + DeviceSpec + 前端行为执行器` 跑通；稳定后再让 `SceneBehaviorGraph` 接管更复杂的调度语义。

## 6. 一句话总结

当前执行链路不是“signal 直接调用任意回调函数”，而是：

```text
SceneDocument 定义场景和连接；
TopologyGraph 派生信号拓扑；
SignalBusRuntime 投递信号；
DeviceRuntime 根据目标 signal 查 DeviceSpec 并解析 behavior_id；
后端发布 device_behavior_triggered；
前端根据 behavior_id 和 payload 执行动画；
前端完成后回调后端，后端继续推进下一轮事件。
```
