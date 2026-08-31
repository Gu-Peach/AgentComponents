# Nodes

节点按 LangGraph 类型拆分：

| 文件 | 节点类型 | 说明 |
|---|---|---|
| `context.py` | Tool Nodes + Model Node | 加载 SceneDocument、加载 DeviceSpec、解析意图、连接校验。 |
| `modeling.py` | Model Nodes + Policy Tool Node | 场景理解、能力摘要、模块分解、事件状态建模、行为规则建模、策略合成。 |
| `validation.py` | Tool Nodes + Interrupt Node | 组装、校验、修复、解释、人工确认、最终写入。 |
| `routers.py` | Conditional Edge helpers | 根据 `AgentState` 决定 LangGraph 分支。 |
