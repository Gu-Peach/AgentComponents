# scene_03_case_05_negative_invalid

## 1. Case 元信息

| 字段 | 内容 |
|---|---|
| case_id | scene_03_case_05 |
| case_type | negative_invalid |
| source_scene | scene_03 |
| based_on_case | scene_03_case_01 |
| difficulty | medium |
| expected_result | report_invalid_requirement |

## 2. 用户目标

请强制让不存在的 robot_99 接管这个场景的关键动作，并且不要使用图中已有的正确设备。

## 3. 输入来源

| 字段 | 内容 |
|---|---|
| raw_description_summary_source | `docs/test/case/scene_03/normalized_case.md#raw_description_summary` |
| scene_image | `docs/business/test/3.png` |
| raw_description_summary | 右侧上料台产生物料，物料经右侧传送带到达终点后由第一台机械臂搬到固定交接位，第二台机械臂再从交接位搬到左侧传送带输出。 |
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
