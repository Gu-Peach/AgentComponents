# Graph

本目录保存 `SceneBehaviorGraph` Agent 的 LangGraph 编排代码。

## 文件说明

| 文件 | 作用 |
|---|---|
| `builder.py` | 构建真实 LangGraph `StateGraph`，声明节点和条件边。 |
| `app.py` | LangGraph CLI/Studio 入口，导出 `graph`。 |
| `runner.py` | 本地 fallback runner；未安装 `langgraph` 时按相同节点顺序执行。 |

## 主图

```text
START
  -> load_scene
  -> load_device_specs
  -> parse_intent
  -> validate_connections
  -> understand_scene
  -> summarize_capabilities
  -> decompose_process
  -> model_event_state
  -> model_behavior_rules
  -> synthesize_policies
  -> assemble_graph
  -> validate_graph
  -> explain
  -> human_review
  -> finalize
  -> END
```

`validate_connections`、`validate_graph`、`human_review` 使用 conditional edges 控制是否继续、修复、回退或结束。
