# Input: scene_06_case_04

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
请重点验证连续输送到离散事件的转换：停留点占用、满载阻塞、释放恢复、加工或定位完成后再进入下一步。
```

## 4. case_delta

基于 case_01 的连续-离散变体：强调停留点、阻塞、释放、完成事件与状态迁移。

## 5. expected_result

```text
generate_valid_graph
```
