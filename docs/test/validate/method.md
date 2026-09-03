# SceneBehaviorGraph Agent 验证方法索引

本目录保存 `SceneBehaviorGraph Agent` 的验证方法文档。

## 方法文档

| 文档 | 说明 |
|---|---|
| `method/semantic_quantitative_evaluation.md` | 调度结果准确性的语义量化比对方法，包含现有 Agent / LLM / 图结构验证方法调研、语义单元抽取、相似度计算、二分图匹配、Precision / Recall / F1、trace 校验、加权总分和论文实验呈现建议。 |

## 当前推荐口径

- 图合规性：使用脚本做确定性 schema 校验。
- 调度结果准确性：使用 `semantic_quantitative_evaluation.md` 中的语义单元匹配与加权评分。
- 最终报告：同时输出单 case 维度分数和全量 benchmark 汇总分数。
