# Scene Layout JSON 输出协议

## 目标

`Scene Layout JSON` 是场景搭建完成后的核心输出。它既保存当前布局，也保存 Interface 工作区中手动编排的工艺流程，并为 agent 生成仿真执行计划提供稳定输入。

这份 JSON 可以看作 demo 场景文件的扩展版本：demo 更偏向描述场景资源和设备配置，本协议在此基础上增加了 `processFlow` 和可选的 `compiledPlan`，让 agent 能理解“设备如何连接、物料如何流动、仿真应如何执行”。

## 输出内容

### `metadata`

记录文档自身信息，包括场景 ID、名称、创建时间和单位。它用于实验记录、版本追踪和后续结果复现。

### `layout`

保存场景中的设备布局，是用户搭建场景的源数据。

每个设备应包含：

- `id`：场景内唯一设备 ID。
- `name`：用户可读设备名称。
- `type`：设备类型，如 `conveyor`、`robot`、`workpiece`。
- `catalogId`：来源目录中的资产 ID。
- `modelUrl`：模型文件路径。
- `interfaceUrl`：接口配置文件路径。
- `transform`：设备当前的位置、旋转和缩放。

这一层回答的问题是：场景里有什么设备，它们摆在哪里。

### `processFlow`

保存 Interface 工作区中的工艺流程连接关系，是用户编排结果的核心。

连接使用流程口，而不是直接暴露设备的物理接口：

- `sourceDeviceId`
- `sourceInterface`
- `targetDeviceId`
- `targetInterface`

例如 `conveyor_1.flow_output -> robot_1.flow_input` 表示物料从传送带流向机械臂。设备真实接口仍由 `interfaceUrl` 指向的接口配置解释，用于后续坐标提取、对齐和执行参数生成。

这一层回答的问题是：物料按什么流程流转。

### `simulation`

保存仿真执行策略和关键运行约定。

当前建议包含：

- `workpieceDeviceId`：作为物料被执行对象的设备 ID。
- `workpieceNodeName`：模型中物料根节点名。
- `executionPolicy.conveyorAlwaysRunsEntryToExit`：只要出现传送带动作，就完整执行 `entry -> exit`。
- `executionPolicy.robotPlaceHeight`：机器人放置时移动到目标入口上方的高度，目前为 `1`。
- `executionPolicy.robotUsesRuntimeEndEffectorStart`：机器人 IK 执行时使用运行时真实末端位置作为轨迹起点。
- `interfaceCoordinateMode`：接口坐标解释方式，当前为世界坐标。

这一层回答的问题是：相同流程应该按什么规则执行。

### `compiledPlan`

`compiledPlan` 是可选的执行快照，由 `layout + processFlow + simulation` 推导得到。

建议保存它用于实验验证和结果复现，但不要把它作为唯一事实来源。真正的源数据仍然是 `layout` 和 `processFlow`，因为接口标准、执行策略或 agent 规划策略升级后，可以重新生成新的执行计划。

这一层回答的问题是：当前这次导出推导出的执行段是什么。

## Agent 使用方式

Agent 应优先读取：

1. `layout.devices`：理解场景中有哪些设备、设备类型和模型接口来源。
2. `processFlow.connections`：理解工艺流程顺序。
3. `simulation.executionPolicy`：理解仿真规则。

随后 agent 可以调用编译逻辑生成执行计划：

```text
Scene Layout JSON -> compileSceneLayoutToExecutionPlan -> ExecutionPlan -> Simulation Runtime
```

如果 JSON 中包含 `compiledPlan`，agent 可以将其作为参考或验证对象，但仍应允许系统基于源数据重新编译。

## 仿真执行语义

当前阶段的基础语义如下：

- conveyor：始终执行 `entry -> exit`，即物料底部接口沿传送带入口到出口移动。
- robot：末端执行器沿轨迹点移动，关节由 IK 求解器联动。
- robot pickup：机器人先移动到物料当前顶部接口点，到达后绑定物料。
- robot place：机器人移动到下一个设备入口上方 `robotPlaceHeight`，然后解除绑定，并将物料底部接口放置到目标入口。
- workpiece：不作为流程主动节点，只作为物料流转中的被执行对象。

## 实验验证作用

这份 JSON 可以作为实验结果验证文档，记录一次实验的完整输入：

- 场景设备和布局是否一致。
- 工艺流程连接是否一致。
- 仿真策略是否一致。
- 编译出的执行段是否一致。
- 预期行为是否与实际播放结果一致。

因此，实验报告中可以引用同一份 `Scene Layout JSON`，并附带执行日志、观察结果或失败原因。

## 模板位置

当前模板文件位于：

```text
frontend/public/process_test/scene-layout.template.json
```

后续可以基于该模板实现导出功能：

```text
sceneStore.devices + sceneStore.interfaceConnections
  -> exportSceneLayout()
  -> scene-layout.json
```
