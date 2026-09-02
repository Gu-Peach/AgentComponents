# Input: scene_03_case_01

## 1. raw_description_summary

来源：`docs/test/case/scene_03/normalized_case.md#raw_description_summary`

```text
右侧上料台产生物料，物料经右侧传送带到达终点后由第一台机械臂搬到固定交接位，第二台机械臂再从交接位搬到左侧传送带输出。
```

## 2. scene_image

```text
docs/business/test/3.png
```

请根据场景图片确认设备布局、连接方向、物料位置、机械臂可达关系、传送带方向和可能的断点 / 占位点。

## 3. case_user_goal

```text
请按图里的布局跑一遍双机械臂固定交接位搬运线，让物料按场景描述完成基础流程，传送带要按停留点排队，不要把物料瞬移到终点。
```

## 4. case_delta

无。

## 5. expected_result

```text
generate_valid_graph
```
