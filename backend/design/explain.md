# SignalBusRuntime 实际案例说明

更新时间：2026-09-07

这份文档用一个具体案例解释当前后端 `SignalBusRuntime.emit()` 的投递链路：它不是在模拟机械臂真实运动，而是在验证“信号能沿场景连线流动，并产生可观察的运行态变化”。

## 1. 案例背景

场景里有两台设备：

```text
conveyor_1：传送带
robot_1：机械臂
```

业务含义是：

```text
传送带检测到物料到达出口
  -> 发出 conveyor_1.part_ready = true
  -> 机械臂收到 robot_1.start_pick = true
  -> 后端生成一个“机械臂待抓取任务”
```

注意：当前 Phase 1 不执行真实抓取动作，也不模拟运动耗时。它只生成一个 `pending device_task`，表示“机械臂已经收到启动抓取的信号，后续调度器/设备 runtime 可以消费这个任务”。

## 2. 场景里的信号边

当前投递依据来自 `SceneDocument.signal_edges[]`。这个案例需要一条信号边：

```json
{
  "edge_id": "sig_conveyor_to_robot",
  "source": "conveyor_1.part_ready",
  "target": "robot_1.start_pick",
  "edge_type": "control_signal",
  "delivery": "event",
  "trigger": "on_rising_edge",
  "transform": { "type": "identity" },
  "enabled": true,
  "route_id": "route_conveyor_to_robot"
}
```

字段含义：

| 字段        | 在这个案例中的含义                                                                                                                                                                                                   |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `source`    | 谁发信号：传送带的 `part_ready` 输出信号                                                                                                                                                                             |
| `target`    | 谁收信号：机械臂的 `start_pick` 输入信号                                                                                                                                                                             |
| `delivery`  | 投递语义，当前只是记录到事件里；这里表示一次事件投递                                                                                                                                                                 |
| `trigger`   | 触发条件；`on_rising_edge(上升沿触发。意思是：信号从 低/假/未激活 变成 高/真/激活 的那一瞬间才触发。上一次 conveyor_1.part_ready = false这一次 conveyor_1.part_ready = true=> 触发)` 表示从 false/空变成 true 时触发 |
| `transform` | 信号转换；`identity` 表示 value 和 payload 原样传给 target                                                                                                                                                           |
| `enabled`   | 是否启用这条边；false 时不会投递                                                                                                                                                                                     |

关键点：`delivery` 是这条信号边的投递语义，不是 target signal 自身的属性。当前版本不会因为 `delivery=event/latest_value/command/broadcast` 执行不同调度策略，只会把它记录进 routed event，留给后续 Runtime 使用。

## 3. 外部调用

当传送带检测到物料到达出口时，前端或仿真控制器调用：

```http
POST /api/simulation-runs/{run_id}/signals/conveyor_1.part_ready/emit
```

请求体：

```json
{
  "value": true,
  "payload": {
    "material_id": "part_001"
  },
  "sim_time_s": 1.5
}
```

这句话的业务含义是：

```text
在仿真时间 1.5s，传送带 conveyor_1 说：part_001 已经 ready。
```

## 4. 后端实际投递链路

当前实现链路如下：

```text
API emit request
  -> SimulationService.emit_signal(...)
  -> SignalBusRuntime.emit(run, "conveyor_1.part_ready", payload)
  -> 读取 scene.current_document.signal_edges[]
  -> 找到 source == "conveyor_1.part_ready" 且 enabled=true 的边
  -> 判断 trigger 是否满足
  -> identity transform 原样传递 value/payload
  -> 写入 target signal: robot_1.start_pick = true
  -> 记录 routed_signal_event
  -> 解析 target signal 属于 robot_1 的 start_pick 端口
  -> 查 robot_arm_1 DeviceSpec，匹配 behavior_id = pick_and_place
  -> 生成 pending device_task
  -> 更新 RuntimeSnapshot
```

对应到代码入口：

| 步骤         | 代码位置                                     | 作用                                                         |
| ------------ | -------------------------------------------- | ------------------------------------------------------------ |
| API 入口     | `backend/app/api/simulation.py`              | 接收 `/signals/{signal_id}/emit` 请求                        |
| Service 入口 | `backend/app/services/simulation_service.py` | 获取 run，并委托 `SignalBusRuntime.emit()`                   |
| 信号总线     | `backend/app/services/signal_bus_runtime.py` | 执行 source 记录、路由匹配、target 写入、task 生成           |
| 运行态存储   | `backend/app/services/runtime_state.py`      | 写 latest signal、Redis stream、device task stream、snapshot |
| 数据库事件   | `backend/app/db/models.py`                   | `simulation_events` 保存审计事件                             |

## 5. 一步一步看 emit 做了什么

### 5.1 读取旧信号值

`SignalBusRuntime.emit()` 先读取当前 run 里已有的信号值：

```text
previous_signals = runtime_store.get_signals(run.id)
```

目的：判断 `on_rising_edge`、`on_falling_edge`、`on_change` 这类 trigger。

在本案例里，如果之前没有 `conveyor_1.part_ready`，现在 value 是 `true`，则满足：

```text
previous = 空 / false
current = true
trigger = on_rising_edge
结果：触发
```

如果上一次已经是 true，这次又 emit true，那么 `on_rising_edge` 不会再次投递，会进入 `skipped_routes`。

### 5.2 记录 source signal

先把 source 自己写入 latest signal：

```json
{
  "signal_id": "conveyor_1.part_ready",
  "value": true,
  "payload": {
    "material_id": "part_001"
  },
  "delivery": "source_emit"
}
```

它会被写到三处：

```text
RuntimeStateStore latest signals
Redis/InMemory event stream: signal_event
Postgres simulation_events: signal_event
```

同时 `RuntimeSnapshot.signal_values` 会出现：

```json
{
  "conveyor_1.part_ready": true
}
```

### 5.3 匹配 signal edge

然后遍历当前场景里的 `signal_edges[]`：

```text
edge.source == "conveyor_1.part_ready"
edge.enabled == true
```

匹配到这条边：

```text
conveyor_1.part_ready -> robot_1.start_pick
```

如果有多条边都以 `conveyor_1.part_ready` 为 source，就会 fan-out，也就是一个 source 同时投递给多个 target。

### 5.4 判断 trigger

这条边配置的是：

```json
"trigger": "on_rising_edge"
```

当前判断逻辑：

| trigger           | 当前判断方式                                 |
| ----------------- | -------------------------------------------- |
| `manual`          | 永远触发                                     |
| `level`           | 当前 value 为 true 时触发                    |
| `on_change`       | 旧值不存在或旧值 != 新值时触发               |
| `on_falling_edge` | 旧值为 true，新值为 false 时触发             |
| `on_rising_edge`  | 默认逻辑，旧值为空/false，新值为 true 时触发 |

本案例满足 `on_rising_edge`，所以继续投递。

### 5.5 执行 transform

这条边配置的是：

```json
"transform": { "type": "identity" }
```

所以 target 收到的内容和 source 一样：

```json
{
  "value": true,
  "payload": {
    "material_id": "part_001"
  }
}
```

当前只支持 `identity`。如果传入其他 transform，例如 `payload_template`，目前会跳过这条 route，并记录：

```json
{
  "reason": "unsupported_transform"
}
```

### 5.6 写入 target signal 和 routed event

随后写入目标信号：

```json
{
  "signal_id": "robot_1.start_pick",
  "value": true,
  "payload": {
    "material_id": "part_001"
  },
  "source_signal": "conveyor_1.part_ready",
  "target_signal": "robot_1.start_pick",
  "edge_id": "sig_conveyor_to_robot",
  "route_id": "route_conveyor_to_robot",
  "delivery": "event",
  "trigger": "on_rising_edge",
  "transform": { "type": "identity" }
}
```

它会被写到：

```text
RuntimeStateStore latest signals
Redis/InMemory event stream: routed_signal_event
Postgres simulation_events: routed_signal_event
RuntimeSnapshot.event_queue
```

此时 `RuntimeSnapshot.signal_values` 会变成：

```json
{
  "conveyor_1.part_ready": true,
  "robot_1.start_pick": true
}
```

### 5.7 生成 device_task

`SignalBusRuntime` 会解析 target signal：

```text
robot_1.start_pick
  -> instance_id = robot_1
  -> signal_port = start_pick
```

然后从场景实例找到：

```text
robot_1.spec_id = robot_arm_1
```

再读取 `robot_arm_1` 的 DeviceSpec，查 `transport_behaviors[]`：

```json
{
  "behavior_id": "pick_and_place",
  "input_signals": ["start_pick", "resume_pick"],
  "control_signals": ["pause_pick"]
}
```

因为 `start_pick` 在 `input_signals` 中，所以生成：

```json
{
  "task_id": "task_xxx",
  "run_id": "simrun_xxx",
  "instance_id": "robot_1",
  "device_type": "robot_arm",
  "trigger_signal": "robot_1.start_pick",
  "signal_port": "start_pick",
  "behavior_id": "pick_and_place",
  "payload": {
    "material_id": "part_001"
  },
  "status": "pending",
  "source_signal": "conveyor_1.part_ready",
  "route_id": "route_conveyor_to_robot",
  "edge_id": "sig_conveyor_to_robot"
}
```

这个 task 会写到：

```text
RuntimeStateStore device task stream
Postgres simulation_events: device_task_created
RuntimeSnapshot.device_tasks
```

同时，如果 `robot_1` 当前是 idle，则 snapshot 中会被标记成 queued：

```json
{
  "device_states": {
    "robot_1": "queued"
  },
  "device_fsm_states": {
    "robot_1": "queued"
  }
}
```

## 6. 最终返回结果长什么样

API 返回大概是这样：

```json
{
  "signal_id": "conveyor_1.part_ready",
  "value": true,
  "payload": {
    "material_id": "part_001"
  },
  "source_event": {
    "signal_id": "conveyor_1.part_ready",
    "value": true,
    "payload": {
      "material_id": "part_001"
    },
    "delivery": "source_emit"
  },
  "routed_events": [
    {
      "signal_id": "robot_1.start_pick",
      "value": true,
      "payload": {
        "material_id": "part_001"
      },
      "source_signal": "conveyor_1.part_ready",
      "target_signal": "robot_1.start_pick",
      "delivery": "event",
      "route_id": "route_conveyor_to_robot"
    }
  ],
  "device_tasks": [
    {
      "instance_id": "robot_1",
      "signal_port": "start_pick",
      "behavior_id": "pick_and_place",
      "status": "pending"
    }
  ],
  "skipped_routes": [],
  "event_queue_count": 2
}
```

顶层的 `signal_id/value/payload` 仍然是 source signal，这是为了兼容旧 API 使用方；真正的下游投递结果在 `routed_events[]` 和 `device_tasks[]` 里。

## 7. 这个案例和 VC 的对应关系

在 VC 里，类似链路可以理解为：

```text
conveyor_1.part_ready.signal(True)
  -> vcSignal.Connections 找到 robot_1.start_pick
  -> robot_1 的 PythonScript.OnSignal(signal) 被触发
  -> 脚本把任务 append 到 tasks[]
  -> OnRun 后续消费 tasks[]，再执行抓取动作
```

在我们后端里，对应关系是：

```text
SignalBusRuntime.emit("conveyor_1.part_ready", true, payload)
  -> SceneDocument.signal_edges[] 找到 robot_1.start_pick
  -> RuntimeStateStore 写入 robot_1.start_pick
  -> simulation_events 记录 routed_signal_event
  -> device_tasks 生成 robot_1 / pick_and_place / pending
```

所以当前版本相当于复刻了 VC 的前半段：

```text
signal 发出
  -> 沿连接关系投递
  -> 目标设备收到输入
  -> 产生待执行任务
```

还没有复刻后半段：

```text
任务被 OnRun/DeviceRuntime 消费
  -> 执行真实动作
  -> 更新 busy/done/error
  -> 动作完成后继续 emit 下游 signal
```

## 8. 用一句话理解当前实现

当前 `SignalBusRuntime.emit()` 做的是：

```text
把一次 source signal 事件，根据 SceneDocument.signal_edges[] 翻译成一个或多个 target signal 事件，再把目标设备该做的事情登记成 pending device_task。
```

它目前不是设备动作执行器，而是信号投递器 + 任务登记器。

## 9. 为什么这一步有意义

如果没有这一步，系统只能“单点记录某个信号发生了”，但不能证明设备之间的信号关系真的生效。

有了这一步之后，我们可以验证：

```text
传送带发出 part_ready
  -> 机械臂 start_pick 被写入
  -> routed event 可追踪
  -> device task 可观察
  -> snapshot 状态可回放
```

这就是后续接入 `DeviceRuntime`、`runtime_handlers`、FSM、资源锁、动作执行器之前必须先打通的最小闭环。
