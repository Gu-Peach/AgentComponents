# Input: scene_05_case_06

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
按这个场景生成图就行，但我以前叫它 SimPlan，也可能说成 SignalBusSchema；别被名字带偏。实际目标是图里的圆桌双机械臂多出料分拣顺畅运行，谁空谁拿、别堵住、满了就等。
```

## 4. case_delta

基于 case_01 修改：用户目标加入旧 schema 名称、口语化约束和无关称呼；场景事实不变，Agent 应忽略旧方案术语并抽取真实运行目标。

## 5. expected_result

```text
generate_with_assumptions
```
