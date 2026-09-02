# scene_06_case_04_continuous_discrete_event

## 1. Case 元信息

| 字段 | 内容 |
|---|---|
| case_id | scene_06_case_04 |
| case_type | continuous_discrete_event |
| source_scene | scene_06 |
| based_on_case | 无 |
| difficulty | high |
| expected_result | generate_valid_graph |

## 2. 用户目标

请重点验证连续输送到离散事件的转换：停留点占用、满载阻塞、释放恢复、加工或定位完成后再进入下一步。

## 3. 输入来源

| 字段 | 内容 |
|---|---|
| raw_description_summary_source | `docs/test/case/scene_06/normalized_case.md#raw_description_summary` |
| scene_image | `docs/business/test/6.png` |
| raw_description_summary | 出料口间隔出物料，经入口传送带到第一升降台，升降台把物料放入空闲库位；第二升降台从库位取料并送到末端传送带输出。 |
| case_user_goal | 请重点验证连续输送到离散事件的转换：停留点占用、满载阻塞、释放恢复、加工或定位完成后再进入下一步。 |

## 4. 场景修改点

基于 case_01 的连续-离散变体：强调停留点、阻塞、释放、完成事件与状态迁移。

## 5. 主要验证点

- 最终图包含所有必填 section
- 引用的设备和行为必须来自当前 DeviceSpec/SceneDocument
- 传送带必须建模停留点、占位、队列、负载、阻塞和释放
- 连续状态达到阈值后必须产生离散事件和状态迁移

## 6. 期望 Agent 行为

Agent 应基于 `raw_description_summary`、场景图片和本 case 用户目标生成或拒绝生成最终 `SceneBehaviorGraph`；判卷只检查最终图或失败报告，不检查 LangGraph 中间节点。
