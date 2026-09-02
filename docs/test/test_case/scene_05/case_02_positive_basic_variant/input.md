# Input: scene_05_case_02

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
在圆桌双机械臂多出料分拣里优先保证节拍稳定：上游可以连续补料，但下游未释放时要等待；如果有多个目标设备，就按确定性优先级选择。
```

## 4. case_delta

基于 case_01 的正向变体：强调稳定节拍、确定性优先级和下游释放后继续。

## 5. expected_result

```text
generate_valid_graph
```
