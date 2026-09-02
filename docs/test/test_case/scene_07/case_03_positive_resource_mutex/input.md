# Input: scene_07_case_03

## 1. raw_description_summary

来源：`docs/test/case/scene_07/normalized_case.md#raw_description_summary`

```text
输入传送带持续送入物料，机械臂从输入传送带取料到固定加工位模拟加工，完成后放到输出传送带。
```

## 2. scene_image

```text
docs/business/test/7.png
```

请根据场景图片确认设备布局、连接方向、物料位置、机械臂可达关系、传送带方向和可能的断点 / 占位点。

## 3. case_user_goal

```text
这个场景没有真正的多机械臂并行，请重点把单机械臂、共享工位和目标缓存的互斥关系建清楚，允许上游排队等待。
```

## 4. case_delta

基于 case_01 的协作/互斥变体：强调共享资源 claim、资源锁和不会重复占用。

## 5. expected_result

```text
generate_valid_graph
```
