# Input: scene_02_case_03

## 1. raw_description_summary

来源：`docs/test/case/scene_02/normalized_case.md#raw_description_summary`

```text
左侧出料口间隔输出承载 12 个工件的托盘，托盘沿长主传送带移动到三台机械臂工位；系统优先把新托盘送到最远端空闲机械臂，三台机械臂全忙时主线和出料口暂停。
```

## 2. scene_image

```text
docs/business/test/2.png
```

请根据场景图片确认设备布局、连接方向、物料位置、机械臂可达关系、传送带方向和可能的断点 / 占位点。

## 3. case_user_goal

```text
我希望图中的可并行设备一起协作，谁空闲谁先处理，但共享工件、交接位或出口传送带不能被两个动作同时占用。
```

## 4. case_delta

基于 case_01 的协作/互斥变体：强调共享资源 claim、资源锁和不会重复占用。

## 5. expected_result

```text
generate_valid_graph
```
