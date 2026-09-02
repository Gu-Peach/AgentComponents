# scene_07_case_03_positive_basic

## 1. Case 元信息

| 字段 | 内容 |
|---|---|
| case_id | scene_07_case_03 |
| case_type | positive_basic |
| source_scene | scene_07 |
| based_on_case | 无 |
| difficulty | medium |
| expected_result | generate_valid_graph |

## 2. 用户目标

这个场景没有真正的多机械臂并行，请重点把单机械臂、共享工位和目标缓存的互斥关系建清楚，允许上游排队等待。

## 3. 输入来源

| 字段 | 内容 |
|---|---|
| raw_description_summary_source | `docs/test/case/scene_07/normalized_case.md#raw_description_summary` |
| scene_image | `docs/business/test/7.png` |
| raw_description_summary | 输入传送带持续送入物料，机械臂从输入传送带取料到固定加工位模拟加工，完成后放到输出传送带。 |
| case_user_goal | 这个场景没有真正的多机械臂并行，请重点把单机械臂、共享工位和目标缓存的互斥关系建清楚，允许上游排队等待。 |

## 4. 场景修改点

基于 case_01 的协作/互斥变体：强调共享资源 claim、资源锁和不会重复占用。

## 5. 主要验证点

- 最终图包含所有必填 section
- 引用的设备和行为必须来自当前 DeviceSpec/SceneDocument
- 传送带必须建模停留点、占位、队列、负载、阻塞和释放

## 6. 期望 Agent 行为

Agent 应基于 `raw_description_summary`、场景图片和本 case 用户目标生成或拒绝生成最终 `SceneBehaviorGraph`；判卷只检查最终图或失败报告，不检查 LangGraph 中间节点。
