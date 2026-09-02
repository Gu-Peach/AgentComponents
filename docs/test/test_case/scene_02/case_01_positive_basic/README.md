# scene_02_case_01_positive_basic

## 1. Case 元信息

| 字段 | 内容 |
|---|---|
| case_id | scene_02_case_01 |
| case_type | positive_basic |
| source_scene | scene_02 |
| based_on_case | 无 |
| difficulty | medium |
| expected_result | generate_valid_graph |

## 2. 用户目标

请按图里的布局跑一遍多机械臂远端优先托盘分拣线，让物料按场景描述完成基础流程，传送带要按停留点排队，不要把物料瞬移到终点。

## 3. 输入来源

| 字段 | 内容 |
|---|---|
| raw_description_summary_source | `docs/test/case/scene_02/normalized_case.md#raw_description_summary` |
| scene_image | `docs/business/test/2.png` |
| raw_description_summary | 左侧出料口间隔输出承载 12 个工件的托盘，托盘沿长主传送带移动到三台机械臂工位；系统优先把新托盘送到最远端空闲机械臂，三台机械臂全忙时主线和出料口暂停。 |
| case_user_goal | 请按图里的布局跑一遍多机械臂远端优先托盘分拣线，让物料按场景描述完成基础流程，传送带要按停留点排队，不要把物料瞬移到终点。 |

## 4. 场景修改点

无。

## 5. 主要验证点

- 最终图包含所有必填 section
- 引用的设备和行为必须来自当前 DeviceSpec/SceneDocument
- 传送带必须建模停留点、占位、队列、负载、阻塞和释放

## 6. 期望 Agent 行为

Agent 应基于 `raw_description_summary`、场景图片和本 case 用户目标生成或拒绝生成最终 `SceneBehaviorGraph`；判卷只检查最终图或失败报告，不检查 LangGraph 中间节点。
