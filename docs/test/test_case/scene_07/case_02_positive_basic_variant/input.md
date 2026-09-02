# Input: scene_07_case_02

## 1. raw_description_summary

来源：`docs/test/case/scene_07/normalized_case.md#raw_description_summary`

```text
输入传送带持续送入物料，机械臂从输入传送带取料到固定加工位模拟加工，完成后放到输出传送带。
```

## 2. scene_image

```text
docs/business/test/7.png
```

请根据场景图片确认设备布局、连接方向、物料位置、机械臂可达关系、传送带方向和可能的断点 / 占位点。

## 3. case_user_goal

```text
在单机械臂机床加工上下料里优先保证节拍稳定：上游可以连续补料，但下游未释放时要等待；如果有多个目标设备，就按确定性优先级选择。
```

## 4. case_delta

基于 case_01 的正向变体：强调稳定节拍、确定性优先级和下游释放后继续。

## 5. expected_result

```text
generate_valid_graph
```
