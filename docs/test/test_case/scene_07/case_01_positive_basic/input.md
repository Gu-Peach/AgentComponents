# Input: scene_07_case_01

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
请按图里的布局跑一遍单机械臂机床加工上下料，让物料按场景描述完成基础流程，传送带要按停留点排队，不要把物料瞬移到终点。
```

## 4. case_delta

无。

## 5. expected_result

```text
generate_valid_graph
```
