# scene_09_case_06_semantic_interference

## 1. Case 元信息

| 字段 | 内容 |
|---|---|
| case_id | scene_09_case_06 |
| case_type | semantic_interference |
| source_scene | scene_09 |
| based_on_case | scene_09_case_01 |
| difficulty | high |
| expected_result | generate_with_assumptions |

## 2. 用户目标

按这个场景生成图就行，但我以前叫它 SimPlan，也可能说成 SignalBusSchema；别被名字带偏。实际目标是图里的旋转台定位与机械臂下料顺畅运行，谁空谁拿、别堵住、满了就等。

## 3. 输入来源

| 字段 | 内容 |
|---|---|
| raw_description_summary_source | `docs/test/case/scene_09/normalized_case.md#raw_description_summary` |
| scene_image | `docs/business/test/9.png` |
| raw_description_summary | 出料台生成工件，人工搬运简化为旋转台固定工位生成工件；旋转台旋转 90 度后，机械臂抓取工件到工作台，工件消失。 |
| case_user_goal | 按这个场景生成图就行，但我以前叫它 SimPlan，也可能说成 SignalBusSchema；别被名字带偏。实际目标是图里的旋转台定位与机械臂下料顺畅运行，谁空谁拿、别堵住、满了就等。 |

## 4. 场景修改点

基于 case_01 修改：用户目标加入旧 schema 名称、口语化约束和无关称呼；场景事实不变，Agent 应忽略旧方案术语并抽取真实运行目标。

## 5. 主要验证点

- 最终图包含所有必填 section
- 引用的设备和行为必须来自当前 DeviceSpec/SceneDocument
- 旧术语与无关描述不得污染最终图

## 6. 期望 Agent 行为

Agent 应基于 `raw_description_summary`、场景图片和本 case 用户目标生成或拒绝生成最终 `SceneBehaviorGraph`；判卷只检查最终图或失败报告，不检查 LangGraph 中间节点。
