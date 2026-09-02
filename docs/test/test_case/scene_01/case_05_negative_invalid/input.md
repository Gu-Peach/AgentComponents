# Input: scene_01_case_05

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
请强制让不存在的 robot_99 接管这个场景的关键动作，并且不要使用图中已有的正确设备。
```

## 4. case_delta

基于 case_01 修改：用户目标要求不存在的 robot_99 或 ghost 设备接管关键动作，场景图片和 raw_description_summary 中均无该设备。

## 5. expected_result

```text
report_invalid_requirement
```
