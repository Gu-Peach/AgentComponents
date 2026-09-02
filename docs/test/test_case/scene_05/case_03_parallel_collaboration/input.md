# Input: scene_05_case_03

## 1. raw_description_summary

来源：`docs/test/case/scene_05/normalized_case.md#raw_description_summary`

```text
圆桌固定位置生成物料，两台机械臂从圆桌取料并放到空闲出料传送带，多个出料传送带按停留点容量接收物料。
```

## 2. scene_image

```text
docs/business/test/5.png
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
