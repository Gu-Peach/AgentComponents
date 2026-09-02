# Input: scene_09_case_06

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
按这个场景生成图就行，但我以前叫它 SimPlan，也可能说成 SignalBusSchema；别被名字带偏。实际目标是图里的旋转台定位与机械臂下料顺畅运行，谁空谁拿、别堵住、满了就等。
```

## 4. case_delta

基于 case_01 修改：用户目标加入旧 schema 名称、口语化约束和无关称呼；场景事实不变，Agent 应忽略旧方案术语并抽取真实运行目标。

## 5. expected_result

```text
generate_with_assumptions
```
