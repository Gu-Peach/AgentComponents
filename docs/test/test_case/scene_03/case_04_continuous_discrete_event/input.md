# Input: scene_03_case_04

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
请重点验证连续输送到离散事件的转换：停留点占用、满载阻塞、释放恢复、加工或定位完成后再进入下一步。
```

## 4. case_delta

基于 case_01 的连续-离散变体：强调停留点、阻塞、释放、完成事件与状态迁移。

## 5. expected_result

```text
generate_valid_graph
```
