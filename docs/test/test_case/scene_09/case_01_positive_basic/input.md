# Input: scene_09_case_01

## 1. raw_description_summary

来源：`docs/test/case/scene_09/normalized_case.md#raw_description_summary`

```text
出料台生成工件，人工搬运简化为旋转台固定工位生成工件；旋转台旋转 90 度后，机械臂抓取工件到工作台，工件消失。
```

## 2. scene_image

```text
docs/business/test/9.png
```

请根据场景图片确认设备布局、连接方向、物料位置、机械臂可达关系、传送带方向和可能的断点 / 占位点。

## 3. case_user_goal

```text
请按图里的布局跑一遍旋转台定位与机械臂下料，让物料按场景描述完成基础流程，传送带要按停留点排队，不要把物料瞬移到终点。
```

## 4. case_delta

无。

## 5. expected_result

```text
generate_valid_graph
```
