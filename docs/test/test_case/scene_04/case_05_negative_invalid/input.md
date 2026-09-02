# Input: scene_04_case_05

## 1. raw_description_summary

来源：`docs/test/case/scene_04/normalized_case.md#raw_description_summary`

```text
传送带起点直接生成或接收物料，物料移动到中间加工停留点后由机械臂执行固定位置操作，完成后继续沿传送带输出。
```

## 2. scene_image

```text
docs/business/test/4.png
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
