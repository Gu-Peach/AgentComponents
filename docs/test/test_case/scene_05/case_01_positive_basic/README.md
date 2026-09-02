# scene_05_case_01_positive_basic

## 1. Case 元信息

| 字段 | 内容 |
|---|---|
| case_id | scene_05_case_01 |
| case_type | positive_basic |
| source_scene | scene_05 |
| based_on_case | 无 |
| difficulty | medium |
| expected_result | generate_valid_graph |

## 2. 用户目标

请按图里的布局跑一遍圆桌双机械臂多出料分拣，让物料按场景描述完成基础流程，传送带要按停留点排队，不要把物料瞬移到终点。

## 3. 输入来源

| 字段 | 内容 |
|---|---|
| raw_description_summary_source | `docs/test/case/scene_05/normalized_case.md#raw_description_summary` |
| scene_image | `docs/business/test/5.png` |
| raw_description_summary | 圆桌固定位置生成物料，两台机械臂从圆桌取料并放到空闲出料传送带，多个出料传送带按停留点容量接收物料。 |
| case_user_goal | 请按图里的布局跑一遍圆桌双机械臂多出料分拣，让物料按场景描述完成基础流程，传送带要按停留点排队，不要把物料瞬移到终点。 |

## 4. 场景修改点

无。

## 5. 主要验证点

- 最终图包含所有必填 section
- 引用的设备和行为必须来自当前 DeviceSpec/SceneDocument
- 传送带必须建模停留点、占位、队列、负载、阻塞和释放

## 6. 期望 Agent 行为

Agent 应基于 `raw_description_summary`、场景图片和本 case 用户目标生成或拒绝生成最终 `SceneBehaviorGraph`；判卷只检查最终图或失败报告，不检查 LangGraph 中间节点。
