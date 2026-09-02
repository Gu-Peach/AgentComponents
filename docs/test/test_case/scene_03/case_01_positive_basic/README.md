# scene_03_case_01_positive_basic

## 1. Case 元信息

| 字段 | 内容 |
|---|---|
| case_id | scene_03_case_01 |
| case_type | positive_basic |
| source_scene | scene_03 |
| based_on_case | 无 |
| difficulty | medium |
| expected_result | generate_valid_graph |

## 2. 用户目标

请按图里的布局跑一遍双机械臂固定交接位搬运线，让物料按场景描述完成基础流程，传送带要按停留点排队，不要把物料瞬移到终点。

## 3. 输入来源

| 字段 | 内容 |
|---|---|
| raw_description_summary_source | `docs/test/case/scene_03/normalized_case.md#raw_description_summary` |
| scene_image | `docs/business/test/3.png` |
| raw_description_summary | 右侧上料台产生物料，物料经右侧传送带到达终点后由第一台机械臂搬到固定交接位，第二台机械臂再从交接位搬到左侧传送带输出。 |
| case_user_goal | 请按图里的布局跑一遍双机械臂固定交接位搬运线，让物料按场景描述完成基础流程，传送带要按停留点排队，不要把物料瞬移到终点。 |

## 4. 场景修改点

无。

## 5. 主要验证点

- 最终图包含所有必填 section
- 引用的设备和行为必须来自当前 DeviceSpec/SceneDocument
- 传送带必须建模停留点、占位、队列、负载、阻塞和释放

## 6. 期望 Agent 行为

Agent 应基于 `raw_description_summary`、场景图片和本 case 用户目标生成或拒绝生成最终 `SceneBehaviorGraph`；判卷只检查最终图或失败报告，不检查 LangGraph 中间节点。
