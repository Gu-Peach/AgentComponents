# Input: scene_06_case_02

## 1. raw_description_summary

来源：`docs/test/case/scene_06/normalized_case.md#raw_description_summary`

```text
出料口间隔出物料，经入口传送带到第一升降台，升降台把物料放入空闲库位；第二升降台从库位取料并送到末端传送带输出。
```

## 2. scene_image

```text
docs/business/test/6.png
```

请根据场景图片确认设备布局、连接方向、物料位置、机械臂可达关系、传送带方向和可能的断点 / 占位点。

## 3. case_user_goal

```text
在升降台入库出库仓储线里优先保证节拍稳定：上游可以连续补料，但下游未释放时要等待；如果有多个目标设备，就按确定性优先级选择。
```

## 4. case_delta

基于 case_01 的正向变体：强调稳定节拍、确定性优先级和下游释放后继续。

## 5. expected_result

```text
generate_valid_graph
```
