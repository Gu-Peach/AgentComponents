# Validation Report

## 静态通过项

- 使用新方案链路，不包含 SimPlan。
- golden JSON 包含 SceneBehaviorGraph 必需一级字段。
- 行为规则使用 trigger / guard / policy / action。
- 事件统一从 event_bus 注册并路由。
- 传送带场景包含停留点、占用、队列和容量状态。

## 需要后续补充或确认

- 机床是否需要独立设备规范？
- 加工时长与加工成功/失败策略是否固定？

## 需要 Runtime Trace 验证的行为

- 运行期队列推进和停留点释放顺序需要 Runtime trace 验证。
- 资源锁是否正确释放需要 Runtime trace 验证。
- 异常和超时触发 observation 的具体时刻需要 Runtime trace 验证。
