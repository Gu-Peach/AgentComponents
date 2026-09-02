# Input: scene_01_case_01

## 1. raw_description_summary

来源：`docs/test/case/scene_01/normalized_case.md#raw_description_summary`

```text
图 1 是一个托盘分拣场景：左侧托盘承载 12 个工件，中间由两段主传送带串联运输托盘，右侧有两台机械臂和上下两条出料传送带。托盘到位后，空闲机械臂从托盘上取料并放到出料传送带；出料传送带满载时暂停机械臂，恢复容量后继续。
```

## 2. scene_image

```text
docs/business/test/1.png
```

请根据场景图片确认设备布局、连接方向、物料位置、机械臂可达关系、传送带方向和可能的断点 / 占位点。

## 3. case_user_goal

```text
请按图里的布局跑一遍托盘分拣停留点传送线，让物料按场景描述完成基础流程，传送带要按停留点排队，不要把物料瞬移到终点。
```

## 4. case_delta

无。

## 5. expected_result

```text
generate_valid_graph
```
