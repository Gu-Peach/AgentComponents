对，基本就是这个分层思路。更准确地说，我建议当前版本先做一个最小可运行 SignalBusRuntime：
emit source signal
-> 查 SceneDocument.signal_edges[]
-> 找到 target signal
-> 写入 target latest value
-> 记录 routed event
-> 触发一个受控 handler
-> 产生最小状态变更 / device task
当前版本先不碰太多复杂调度，原因是我们需要先验证“信号真的能沿连线流动起来”。否则一上来把资源锁、guard、FSM、调度器、动作执行都混在一起，出问题时很难判断是路由错了，还是设备状态机错了，还是资源抢占错了。
我建议的阶段拆法是：
第一阶段：单向事件投递链路
数据源：直接读 SceneDocument.signal_edges[]。
能力：source -> target fan-out。
支持：enabled、delivery、identity transform、基础事件日志。
状态变更：只做最小变更，比如写 target signal、写 event_queue、生成 device_task。
不做：资源锁、复杂 guard、完整 FSM、动作持续时间、死锁检测。
第二阶段：稳定后接 TopologyGraph
数据源从原始 signal_edges[] 切到 TopologyGraph.signal_graph.edges[]。
好处是：运行时不反复解析 SceneDocument，而是消费编译好的、已校验的运行索引。
同时可以利用 topology warnings、可达性、悬空信号、错连检查。
第三阶段：接设备行为与 FSM
DeviceRuntime.on_signal(...)
runtime_handlers
signal -> behavior 的受控映射
设备状态从 idle -> queued -> busy -> done/error
RuntimeSnapshot.device_fsm_states
RuntimeSnapshot.active_actions
第四阶段：接调度语义
guard
resource locks
capacity check
wait queues
backpressure
timeout / retry
deadlock detection
所以你的表述是对的，只是我会把“触发状态变更”限定得很轻：
当前版本可以触发“事件状态变更”
但不要直接承诺完整“设备物理动作状态机”
比如当前最小版可以做到：
main_conveyor_1.part_ready=True
-> robot_1.start_pick=True
-> RuntimeSnapshot.signal_values.robot_1.start_pick = true
-> event_queue 里出现 routed_signal_event
-> device_tasks 里出现 robot_1 / start_pick / pending
但暂时不做到：
robot_1 真正进入 busy
-> 抓取动作延时
-> 抢占 gripper 资源
-> 校验目标传送带容量
-> 完成后自动 done
这个后面再接。这样架构更稳，验证也清楚。
