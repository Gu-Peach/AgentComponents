# Input: scene_08_case_02

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
在物料与托盘同步到位装载里优先保证节拍稳定：上游可以连续补料，但下游未释放时要等待；如果有多个目标设备，就按确定性优先级选择。
```

## 4. case_delta

基于 case_01 的正向变体：强调稳定节拍、确定性优先级和下游释放后继续。

## 5. expected_result

```text
generate_valid_graph
```
