# Tools

工具层只做确定性读取、校验、模板选择和写入，不在工具内部隐式生成完整行为图。

| 工具 | 说明 |
|---|---|
| `SceneReader` | 读取并规范化 `SceneDocument`。 |
| `DeviceSpecReader` | 读取并索引相关 `DeviceSpec`。 |
| `ConnectionValidator` / `GraphValidator` | 校验显式连接和 `SceneBehaviorGraph` 引用完整性。 |
| `PolicyLibrary` | 提供策略模板，如 `shared_pool_claim`、`backpressure`、`resource_lock`。 |
| `SceneBehaviorGraphWriter` | 组装和写入符合 SimulationSchema 的 `SceneBehaviorGraph`。 |
