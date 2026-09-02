# Input: scene_03_case_05

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
请强制让不存在的 robot_99 接管这个场景的关键动作，并且不要使用图中已有的正确设备。
```

## 4. case_delta

基于 case_01 修改：用户目标要求不存在的 robot_99 或 ghost 设备接管关键动作，场景图片和 raw_description_summary 中均无该设备。

## 5. expected_result

```text
report_invalid_requirement
```
