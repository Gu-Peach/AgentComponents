# scene_09_case_02_positive_basic

## 1. Case 元信息

| 字段 | 内容 |
|---|---|
| case_id | scene_09_case_02 |
| case_type | positive_basic |
| source_scene | scene_09 |
| based_on_case | 无 |
| difficulty | medium |
| expected_result | generate_valid_graph |

## 2. 用户目标

在旋转台定位与机械臂下料里优先保证节拍稳定：上游可以连续补料，但下游未释放时要等待；如果有多个目标设备，就按确定性优先级选择。

## 3. 输入来源

| 字段 | 内容 |
|---|---|
| raw_description_summary_source | `docs/test/case/scene_09/normalized_case.md#raw_description_summary` |
| scene_image | `docs/business/test/9.png` |
| raw_description_summary | 出料台生成工件，人工搬运简化为旋转台固定工位生成工件；旋转台旋转 90 度后，机械臂抓取工件到工作台，工件消失。 |
| case_user_goal | 在旋转台定位与机械臂下料里优先保证节拍稳定：上游可以连续补料，但下游未释放时要等待；如果有多个目标设备，就按确定性优先级选择。 |

## 4. 场景修改点

基于 case_01 的正向变体：强调稳定节拍、确定性优先级和下游释放后继续。

## 5. 主要验证点

- 最终图包含所有必填 section
- 引用的设备和行为必须来自当前 DeviceSpec/SceneDocument

## 6. 期望 Agent 行为

Agent 应基于 `raw_description_summary`、场景图片和本 case 用户目标生成或拒绝生成最终 `SceneBehaviorGraph`；判卷只检查最终图或失败报告，不检查 LangGraph 中间节点。
