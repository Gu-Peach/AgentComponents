# Input: scene_02_case_05

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
请强制让不存在的 robot_99 接管这个场景的关键动作，并且不要使用图中已有的正确设备。
```

## 4. case_delta

基于 case_01 修改：用户目标要求不存在的 robot_99 或 ghost 设备接管关键动作，场景图片和 raw_description_summary 中均无该设备。

## 5. expected_result

```text
report_invalid_requirement
```
