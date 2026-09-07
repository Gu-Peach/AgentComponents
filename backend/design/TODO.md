# SignalBusRuntime TODO

更新时间：2026-09-07  
目标：先实现一个最小可运行的 `SignalBusRuntime`，验证“信号能沿连线流动并产生可观察状态变更”，再逐步接入拓扑索引、设备行为、FSM 和复杂调度语义。

## 1. 当前版本目标

当前版本先实现单向事件投递链路：

```text
emit source signal
  -> 查 SceneDocument.signal_edges[]
  -> 找到 target signal
  -> 写入 target latest value
  -> 记录 routed event
  -> 生成受控 device task
  -> 产生最小状态变更 / device task
```

核心原则：先验证信号路由链路本身，不把资源锁、guard、完整 FSM、动作执行和调度器混在第一版里。

## 2. 分阶段 TODO

### Phase 1：最小单向事件投递链路

状态：已实现，测试覆盖见 `backend/tests/test_signal_bus_runtime.py`。

- [x] 新增 `backend/app/services/signal_bus_runtime.py`。
- [x] 在 `SimulationService.emit_signal()` 中接入 `SignalBusRuntime.emit()`。
- [x] 数据源先直接读取 `SceneDocument.signal_edges[]`。
- [x] 根据 `source signal` 匹配所有启用的 signal edge。
- [x] 支持 source -> target 的一对一和一对多 fan-out。
- [x] 支持 `enabled` 字段，`enabled=false` 的边不投递。
- [x] 支持 `delivery` 的基础记录：`event`、`latest_value`、`command`、`broadcast`。
- [x] 先只实现 `identity` transform，保留原始 `value` 和 `payload`。
- [x] 写入 source signal latest value。
- [x] 写入 target signal latest value。
- [x] 写入 routed signal event。
- [x] 写入 `event_queue` 或等价 Redis stream。
- [x] 生成最小 `device_task`，但不执行真实设备动作。

### Phase 2：切换到 TopologyGraph

- [ ] 将路由数据源从 `SceneDocument.signal_edges[]` 切到 `TopologyGraph.signal_graph.edges[]`。
- [ ] 在仿真 run 创建或启动前确保 topology 已重建。
- [ ] 利用 topology warnings 识别悬空信号、错连信号和无消费者输出信号。
- [ ] 为 reachability / consumers 查询提供 runtime 内部索引。

### Phase 3：设备回调与行为触发

- [ ] 新增 `backend/app/services/device_runtime.py`。
- [ ] 定义 `DeviceRuntime.on_signal(signal_event)`，对标 VC 的 `OnSignal(signal)`。
- [ ] 新增 `backend/app/services/runtime_handlers.py`。
- [ ] 建立 handler registry，按 `device_type + signal_port` 或 `behavior_id` 分发。
- [ ] 通过 handler registry 支持 `signal -> behavior` 的受控映射。
- [ ] 将 pending `device_task` 分发为具体设备动作，例如 `robot_1.start_pick -> pick_and_place`。
- [ ] 消费 `RuntimeSnapshot.event_queue` 中的 routed event。
- [ ] 写入 `RuntimeSnapshot.active_actions`。
- [ ] 扩展 `RuntimeSnapshot.device_fsm_states`，支持 `queued -> busy -> done/error`。

### Phase 4：调度语义增强

- [ ] 引入 guard 检查。
- [ ] 引入 resource locks。
- [ ] 引入 capacity check。
- [ ] 引入 wait queues。
- [ ] 引入 backpressure。
- [ ] 引入 timeout / retry。
- [ ] 引入 deadlock detection。
- [ ] 接入 `ActionExecutor`，让 device task 真正推进 RuntimeSnapshot。
- [ ] 支持动作完成后继续 emit 下游 signal，例如 `robot_1.done -> conveyor.release_waiting_material`。

## 3. 当前版本明确不做

- 不引入 Agent。
- 不引入 LLM 调用。
- 不自动生成 `SceneBehaviorGraph`。
- 不实现复杂全局调度器。
- 不实现完整设备 FSM。
- 不实现真实动作耗时、运动学、碰撞检测或连续时间仿真。
- 不做资源锁、容量互斥、死锁检测。
- 不允许 signal edge 直接绑定任意函数名；必须通过受控 handler registry 分发。

## 4. 最小链路示例

当前最小版应做到：

```text
main_conveyor_1.part_ready = true
  -> robot_1.start_pick = true
  -> RuntimeSnapshot.signal_values.robot_1.start_pick = true
  -> event_queue 出现 routed_signal_event
  -> device_tasks 出现 robot_1 / start_pick / pending
```

当前最小版暂不做到：

```text
robot_1 真正进入 busy
  -> 抓取动作延时
  -> 抢占 gripper 资源
  -> 校验目标传送带容量
  -> 完成后自动 done
```

## 5. VC 对照关系

VC 中的信号事件处理链路：

```text
vcBoolSignal.signal(value)
  -> vcSignal.Connections
  -> PythonScript.OnSignal(signal)
  -> tasks.append(...)
  -> OnRun 消费任务
  -> 调用 machineProcess / Grasp / Release 等动作函数
  -> 动作完成后继续 signal(...)
```

我们当前版本的对应链路：

```text
SignalBusRuntime.emit(source_signal, value, payload)
  -> SceneDocument.signal_edges[]
  -> Redis latest source signal
  -> Redis latest target signal
  -> Redis stream routed event
  -> simulation_events routed_signal_event
  -> SignalBusRuntime 解析 target device signal
  -> 生成 device_task
```

## 6. 验收标准

- [x] `emit` 一个没有消费者的 source signal 时，只记录 source signal 和 source event，不报错。
- [x] `emit` 一个有单个消费者的 source signal 时，target signal 被写入 Redis/RuntimeStateStore。
- [x] `emit` 一个有多个消费者的 source signal 时，所有 target signal 都被 fan-out 写入。
- [x] `enabled=false` 的 signal edge 不产生 routed event。
- [x] `identity` transform 保留原始 `value` 和 `payload`。
- [x] 每次 routed event 都写入 Redis stream 或内存等价事件流。
- [x] 每次 routed event 都写入 `simulation_events`。
- [x] target signal 可触发最小 `device_task`。
- [x] 暂不执行真实动作，device task 状态保持 `pending`。
- [x] 新增自动化测试 `backend/tests/test_signal_bus_runtime.py`，覆盖以上场景。
