# Input: scene_08_case_01

## 1. raw_description_summary

来源：`docs/test/case/scene_08/normalized_case.md#raw_description_summary`

```text
物料侧出料台和传送带持续送料，托盘侧传送带同步运输空托盘；当物料和托盘都到位时，机械臂把物料装到托盘，达到数量后托盘输出。
```

## 2. scene_image

```text
docs/business/test/8.png
```

请根据场景图片确认设备布局、连接方向、物料位置、机械臂可达关系、传送带方向和可能的断点 / 占位点。

## 3. case_user_goal

```text
请按图里的布局跑一遍物料与托盘同步到位装载，让物料按场景描述完成基础流程，传送带要按停留点排队，不要把物料瞬移到终点。
```

## 4. case_delta

无。

## 5. expected_result

```text
generate_valid_graph
```
