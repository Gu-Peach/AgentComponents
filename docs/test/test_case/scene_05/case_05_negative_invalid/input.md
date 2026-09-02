# Input: scene_05_case_05

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
请强制让不存在的 robot_99 接管这个场景的关键动作，并且不要使用图中已有的正确设备。
```

## 4. case_delta

基于 case_01 修改：用户目标要求不存在的 robot_99 或 ghost 设备接管关键动作，场景图片和 raw_description_summary 中均无该设备。

## 5. expected_result

```text
report_invalid_requirement
```
