# Design Documents

本目录保存 `SimulationSchema` 相关的方法论、技术方案和学术方案。

与 schema 目录的边界：

- `1.DeviceSpec/`、`2.SceneDocument/`、`3.RuntimeSnapshot/`、`4.SceneBehaviorGraph/` 保存数据结构规范、示例和字段说明。
- `design/` 保存 Agent、Runtime、存储、调度算法和论文创新点等方案文档。
- schema 规范可以被 Runtime 直接消费；design 文档用于解释为什么这样设计、后续如何实现。

当前文档：

| 文档 | 内容 |
|---|---|
| [`agent_scene_behavior_graph_design.md`](agent_scene_behavior_graph_design.md) | Agent 生成 `SceneBehaviorGraph` 的技术方案、Runtime 调度方案、存储方案和学术创新点。 |
