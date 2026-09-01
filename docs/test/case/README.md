# SceneBehaviorGraph Benchmark Cases

本目录保存 9 个场景的 Agent benchmark。每个场景目录都按当前 prompt 产出 `README.md`、`normalized_case.md`、`scene_behavior_graph.golden.json`、`graph_explanation.md`、`test_assertions.json` 和 `validation_report.md`。

| Case | 场景 | 图片 | 状态 |
|---|---|---|---|
| `scene_01` | 托盘分拣场景 | `docs/business/test/1.png` | 已建立 normalized / golden / assertions |
| `scene_02` | 多机械臂远端优先托盘分拣线 | `docs/business/test/2.png` | 已建立 normalized / golden / assertions |
| `scene_03` | 双机械臂接力运输机构 | `docs/business/test/3.png` | 已建立 normalized / golden / assertions |
| `scene_04` | 传送带中段机械臂加工模拟 | `docs/business/test/4.png` | 已建立 normalized / golden / assertions |
| `scene_05` | 圆桌双机械臂多出料分拣 | `docs/business/test/5.png` | 已建立 normalized / golden / assertions |
| `scene_06` | 仓储柜双升降台入库出库 | `docs/business/test/6.png` | 已建立 normalized / golden / assertions |
| `scene_07` | 机床旁机械臂加工转运 | `docs/business/test/7.png` | 已建立 normalized / golden / assertions |
| `scene_08` | 物料与托盘同步到位装载 | `docs/business/test/8.png` | 已建立 normalized / golden / assertions |
| `scene_09` | 旋转台定位与机械臂下料 | `docs/business/test/9.png` | 已建立 normalized / golden / assertions |

所有 case 均只使用新方案：`DeviceSpec + SceneDocument + 用户目标 -> SceneBehaviorGraph -> RuntimeSnapshot`。传送带场景必须建模停留点 / 占位点，不允许把物料直接从 entry 移动到 exit。
