# Expected Answer: scene_08_case_05

## 1. Case 修改说明

| 字段 | 内容 |
|---|---|
| based_on_case | scene_08_case_01 |
| 修改类型 | 缺设备实例 / 不支持硬编 |
| 修改内容 | 用户目标要求不存在的 `robot_99` 或 ghost 设备接管关键动作。 |

## 2. 期望 Agent 行为

- Agent 不应硬编非法 `SceneBehaviorGraph`。
- Agent 必须明确指出目标设备不在 `SceneDocument.instances` 或场景图片中。
- Agent 可以输出结构化失败报告；若输出草案，必须在 `goal.assumptions` 与 `failure_observations` 中标注风险。

## 3. 必须识别的问题

| 问题 ID | 问题描述 | 应出现的位置 |
|---|---|---|
| missing_instance | 用户引用不存在设备。 | `failure_observations` / explanation |
| no_safe_graph | 无法用已有设备替代用户强制指定设备。 | `goal.assumptions` / explanation |

## 4. 不允许出现的错误输出

- 不允许凭空发明不存在的设备。
- 不允许凭空发明不存在的 `behavior_id`。
- 不允许忽略缺失连接继续生成完整成功图。
- 不允许输出旧 schema。

## 5. 规范层面答案

如果输出 `SceneBehaviorGraph` 草案，仍必须包含九个必填 section；如果拒绝生成最终图，则必须输出清晰失败报告。
