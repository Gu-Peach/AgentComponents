# scene_01_case_05_negative_invalid

## 1. Case 元信息

| 字段 | 内容 |
|---|---|
| case_id | scene_01_case_05 |
| case_type | negative_invalid |
| source_scene | scene_01 |
| based_on_case | scene_01_case_01 |
| difficulty | medium |
| expected_result | report_invalid_requirement |

## 2. 用户目标

请强制让不存在的 robot_99 接管这个场景的关键动作，并且不要使用图中已有的正确设备。

## 3. 输入来源

| 字段 | 内容 |
|---|---|
| raw_description_summary_source | `docs/test/case/scene_01/normalized_case.md#raw_description_summary` |
| scene_image | `docs/business/test/1.png` |
| raw_description_summary | 图 1 是一个托盘分拣场景：左侧托盘承载 12 个工件，中间由两段主传送带串联运输托盘，右侧有两台机械臂和上下两条出料传送带。托盘到位后，空闲机械臂从托盘上取料并放到出料传送带；出料传送带满载时暂停机械臂，恢复容量后继续。 |
| case_user_goal | 请强制让不存在的 robot_99 接管这个场景的关键动作，并且不要使用图中已有的正确设备。 |

## 4. 场景修改点

基于 case_01 修改：用户目标要求不存在的 robot_99 或 ghost 设备接管关键动作，场景图片和 raw_description_summary 中均无该设备。

## 5. 主要验证点

- 最终图包含所有必填 section
- 引用的设备和行为必须来自当前 DeviceSpec/SceneDocument
- 传送带必须建模停留点、占位、队列、负载、阻塞和释放
- 必须报告不存在设备/能力，不得硬编成功图

## 6. 期望 Agent 行为

Agent 应基于 `raw_description_summary`、场景图片和本 case 用户目标生成或拒绝生成最终 `SceneBehaviorGraph`；判卷只检查最终图或失败报告，不检查 LangGraph 中间节点。
