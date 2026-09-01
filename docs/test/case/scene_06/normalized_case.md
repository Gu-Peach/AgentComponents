# Scene 06：仓储柜双升降台入库出库 Normalized Case

## case_id

`scene_06_storage_rack_dual_lift_buffering`

## source_image

`docs/business/test/6.png`

## raw_description_summary

出料口间隔出物料，经入口传送带到第一升降台，升降台把物料放入空闲库位；第二升降台从库位取料并送到末端传送带输出。

## normalized_user_goal

左侧出料口按节拍生成物料，物料进入入口传送带并按停留点前进到第一升降台。第一升降台空闲且仓储柜存在空库位时，接收物料、移动到对应高度并将物料存入库位。第一升降台工作时，入口传送带出口物料等待，后续物料依次停在上游停留点。第二升降台根据出库策略从仓储柜取出物料，移动到末端传送带对接高度并释放物料。末端传送带按停留点运输到出口后物料离开系统。

## device_inventory

| device_type | instance_id | spec_id | role |
|---|---|---|---|
| `material_source_station` | `source_station_1` | `material_source_station_1` | 入口物料来源 |
| `conveyor` | `inbound_conveyor_1` | `conveyor_1` | 入库入口传送带 |
| `lift_table` | `inbound_lift_1` | `lift_table_1` | 入库升降台 |
| `storage_rack` | `storage_rack_1` | `storage_rack_1` | 仓储柜 / 货架 |
| `lift_table` | `outbound_lift_1` | `lift_table_1` | 出库升降台 |
| `conveyor` | `outbound_conveyor_1` | `conveyor_1` | 末端出库传送带 |

## material_inventory

- `part_001`
- `part_002`
- `part_003`
- `part_004`
- `part_005`
- `part_006`

## process_flow_summary

```text
source_station_1 -> inbound_conveyor_1 stop points -> inbound_lift_1 -> storage_rack_1 cells -> outbound_lift_1 -> outbound_conveyor_1 stop points -> exit
```

## key_runtime_constraints

- 入口升降台一次只能搬运一个物料。
- 库位必须先 reserve 再 store。
- 入口传送带在升降台忙时按停留点排队。
- 末端传送带出口释放后物料消失。

## assumptions

- 存储柜 baseline 使用 first_available 库位策略。
- 出库策略为 FIFO 或按最早入库顺序。
- 升降台高度与库位层级映射由 Runtime 根据 storage cell 解析。

## open_questions

- 入库和出库是否同时进行？
- 是否需要指定目标库位而不是 first_available？
