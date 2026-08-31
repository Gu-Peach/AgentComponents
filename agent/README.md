# Agent

本目录保存基于 LangGraph 设计的 `SceneBehaviorGraph` 生成 Agent。

当前实现目标：

- 按 `docs/design/agent_design.md` 拆分 LangGraph 风格目录结构。
- 提供 `AgentState`、Tool Nodes、Model Nodes、Graph 编排和 demo runner。
- 生成结果符合 `docs/business/SimulationSchema/4.SceneBehaviorGraph` 中的核心结构。
- Runtime 调度器不在本目录实现；Agent 只负责离线生成 `SceneBehaviorGraph`。

## 目录结构

```text
agent/
  scene_behavior_agent/
    schemas/      # AgentState、配置、校验结果等类型定义
    tools/        # SceneReader、DeviceSpecReader、GraphValidator、PolicyLibrary、Writer
    nodes/        # LangGraph 节点函数，区分 model node / tool node / interrupt node
    graph/        # LangGraph 编排入口和 fallback sequential runner
    capabilities/ # Checkpointer、event streaming、memory/store 适配层
    models/       # LLM client 协议与 deterministic fallback model
    examples/     # 本地 demo runner
    tests/        # 轻量验证脚本
```

## 快速运行

```bash
python3 -m agent.scene_behavior_agent.examples.run_demo
```

也可以通过 CLI 指定输入：

```bash
python3 -m agent.scene_behavior_agent.cli \
  --scene docs/business/SimulationSchema/demo/pallet_sorting_line/full_chain_schema.json \
  --goal "托盘到位后由两台机械臂持续分拣物料" \
  --output /tmp/scene_behavior_graph.json
```

如果本地安装了 `langgraph`，可以使用 `agent/langgraph.json` 暴露的图入口：

```text
scene_behavior_agent: ./scene_behavior_agent/graph/app.py:graph
```

输出默认写入：

```text
agent/scene_behavior_agent/examples/output/scene_behavior_graph.generated.json
```
