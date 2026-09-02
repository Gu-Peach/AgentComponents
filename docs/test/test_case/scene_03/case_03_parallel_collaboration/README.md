# scene_03_case_03_parallel_collaboration

## 1. Case 元信息

| 字段 | 内容 |
|---|---|
| case_id | scene_03_case_03 |
| case_type | parallel_collaboration |
| source_scene | scene_03 |
| based_on_case | 无 |
| difficulty | high |
| expected_result | generate_valid_graph |

## 2. 用户目标

我希望图中的可并行设备一起协作，谁空闲谁先处理，但共享工件、交接位或出口传送带不能被两个动作同时占用。

## 3. 输入来源

| 字段 | 内容 |
|---|---|
| raw_description_summary_source | `docs/test/case/scene_03/normalized_case.md#raw_description_summary` |
| scene_image | `docs/business/test/3.png` |
| raw_description_summary | 右侧上料台产生物料，物料经右侧传送带到达终点后由第一台机械臂搬到固定交接位，第二台机械臂再从交接位搬到左侧传送带输出。 |
| case_user_goal | 我希望图中的可并行设备一起协作，谁空闲谁先处理，但共享工件、交接位或出口传送带不能被两个动作同时占用。 |

## 4. 场景修改点

基于 case_01 的协作/互斥变体：强调共享资源 claim、资源锁和不会重复占用。

## 5. 主要验证点

- 最终图包含所有必填 section
- 引用的设备和行为必须来自当前 DeviceSpec/SceneDocument
- 传送带必须建模停留点、占位、队列、负载、阻塞和释放
- 并行执行必须通过共享池 claim 和 resource_lock 避免重复占用

## 6. 期望 Agent 行为

Agent 应基于 `raw_description_summary`、场景图片和本 case 用户目标生成或拒绝生成最终 `SceneBehaviorGraph`；判卷只检查最终图或失败报告，不检查 LangGraph 中间节点。
