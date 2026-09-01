# Validation Report

## 静态通过项

- 使用新方案链路，不包含 SimPlan。
- golden JSON 包含 SceneBehaviorGraph 必需一级字段。
- 行为规则使用 trigger / guard / policy / action。
- 事件统一从 event_bus 注册并路由。

## 需要后续补充或确认

- 工作台是否需要独立 DeviceSpec？
- 旋转台是否有多个工件并行工位？

## 需要 Runtime Trace 验证的行为

- 运行期队列推进和停留点释放顺序需要 Runtime trace 验证。
- 资源锁是否正确释放需要 Runtime trace 验证。
- 异常和超时触发 observation 的具体时刻需要 Runtime trace 验证。
