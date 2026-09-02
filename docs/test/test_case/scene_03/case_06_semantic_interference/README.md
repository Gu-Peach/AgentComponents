# scene_03_case_06_semantic_interference

## 1. Case 元信息

| 字段 | 内容 |
|---|---|
| case_id | scene_03_case_06 |
| case_type | semantic_interference |
| source_scene | scene_03 |
| based_on_case | scene_03_case_01 |
| difficulty | high |
| expected_result | generate_with_assumptions |

## 2. 用户目标

按这个场景生成图就行，但我以前叫它 SimPlan，也可能说成 SignalBusSchema；别被名字带偏。实际目标是图里的双机械臂固定交接位搬运线顺畅运行，谁空谁拿、别堵住、满了就等。

## 3. 输入来源

| 字段 | 内容 |
|---|---|
| raw_description_summary_source | `docs/test/case/scene_03/normalized_case.md#raw_description_summary` |
| scene_image | `docs/business/test/3.png` |
| raw_description_summary | 右侧上料台产生物料，物料经右侧传送带到达终点后由第一台机械臂搬到固定交接位，第二台机械臂再从交接位搬到左侧传送带输出。 |
| case_user_goal | 按这个场景生成图就行，但我以前叫它 SimPlan，也可能说成 SignalBusSchema；别被名字带偏。实际目标是图里的双机械臂固定交接位搬运线顺畅运行，谁空谁拿、别堵住、满了就等。 |

## 4. 场景修改点

基于 case_01 修改：用户目标加入旧 schema 名称、口语化约束和无关称呼；场景事实不变，Agent 应忽略旧方案术语并抽取真实运行目标。

## 5. 主要验证点

- 最终图包含所有必填 section
- 引用的设备和行为必须来自当前 DeviceSpec/SceneDocument
- 传送带必须建模停留点、占位、队列、负载、阻塞和释放
- 旧术语与无关描述不得污染最终图

## 6. 期望 Agent 行为

Agent 应基于 `raw_description_summary`、场景图片和本 case 用户目标生成或拒绝生成最终 `SceneBehaviorGraph`；判卷只检查最终图或失败报告，不检查 LangGraph 中间节点。
