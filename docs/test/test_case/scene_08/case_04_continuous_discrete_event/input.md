# Input: scene_08_case_04

## 1. raw_description_summary

来源：`docs/test/case/scene_08/normalized_case.md#raw_description_summary`

```text
物料侧出料台和传送带持续送料，托盘侧传送带同步运输空托盘；当物料和托盘都到位时，机械臂把物料装到托盘，达到数量后托盘输出。
```

## 2. scene_image

```text
docs/business/test/8.png
```

请根据场景图片确认设备布局、连接方向、物料位置、机械臂可达关系、传送带方向和可能的断点 / 占位点。

## 3. case_user_goal

```text
请重点验证连续输送到离散事件的转换：停留点占用、满载阻塞、释放恢复、加工或定位完成后再进入下一步。
```

## 4. case_delta

基于 case_01 的连续-离散变体：强调停留点、阻塞、释放、完成事件与状态迁移。

## 5. expected_result

```text
generate_valid_graph
```
