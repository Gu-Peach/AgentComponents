# docs/test/test_case 规范校验摘要

校验时间：2026-09-02

## 1. 校验范围

- 目录：`docs/test/test_case`
- 场景数：9
- case 数：54
- JSON 文件数：108
- 校验对象：每个 case 下的 `README.md`、`input.md`、`scene_behavior_graph.golden.json`、`expected_answer.md`、`test_assertions.json`

## 2. 通过项

| 项目 | 结果 |
|---|---|
| 每个场景至少 6 个 case | 通过，9 个场景均为 6 个 case |
| 每个 case 必备文件 | 通过，未发现缺失文件 |
| JSON 可解析性 | 通过，108 个 JSON 文件均可解析 |
| `scene_behavior_graph.golden.json` 顶层必填 section | 通过 |
| `schema_type == SceneBehaviorGraph` | 通过 |
| 旧 schema 字段污染 | 未发现 |
| `event_bus.events` 基础结构 | 通过 |
| `event_bus.routes` 基础结构 | 通过 |
| `behavior_rules` 基础结构 | 通过 |
| `policies` 类型 | 通过，符合当前模板中的 object/map 写法 |
| `test_assertions.json.input_assertions` | 通过，包含 `raw_description_summary_source`、`scene_image` 和相关 flag |
| `input.md` 输入来源 | 通过，包含 `raw_description_summary` 与对应 `docs/business/test/X.png` 场景图片 |

## 3. 不符合最新 prompt 的问题

当前所有 54 个 `scene_behavior_graph.golden.json` 都缺少最新 prompt 要求的输入追踪字段：

| 问题 | 数量 | 说明 |
|---|---:|---|
| `goal.raw_description_summary` 或 `goal.raw_description_summary_source` 缺失 | 54 | golden 图没有把原始场景摘要写入 `goal`。 |
| `goal.scene_image` 缺失 | 54 | golden 图没有记录对应场景图片路径。 |

示例文件：

- `docs/test/test_case/scene_01/case_01_positive_basic/scene_behavior_graph.golden.json`
- `docs/test/test_case/scene_02/case_01_positive_basic/scene_behavior_graph.golden.json`
- `docs/test/test_case/scene_09/case_06_semantic_interference/scene_behavior_graph.golden.json`

## 4. 结论

按当前 `SceneBehaviorGraph` 基础 schema 看，`docs/test/test_case` 下的案例整体结构是合规的：文件完整、JSON 可解析、顶层结构完整、未发现旧 schema 污染。

按最新 `prompt.md` 的更严格要求看，所有 golden 图都需要补充输入追踪字段：

```json
"goal": {
  "raw_description_summary_source": "docs/test/case/scene_XX/normalized_case.md#raw_description_summary",
  "raw_description_summary": "...",
  "scene_image": "docs/business/test/X.png",
  "natural_language": "...",
  "assumptions": []
}
```

## 5. 建议修复顺序

1. 批量为 54 个 `scene_behavior_graph.golden.json` 的 `goal` 补充 `raw_description_summary_source`、`raw_description_summary` 和 `scene_image`。
2. 同步 `docs/test/test_case/prompt.md` 与根目录 `prompt.md`，避免后续继续按旧 prompt 生成 case。
3. 补完后重新运行同样的结构校验，确认剩余问题为 0。
