1.首先场景如下面两张图片所示
E:\project\agent\else\test\2.png
E:\project\agent\else\test\1.png。整个场景的结构数据应该是由单个单个的设备结构组成，所以功能上需要实现场景单个设备的添加和删去。后端接口可能需要调整？

2.  我之前在前端源码中设置了两种接口
    物理/真实接口：来自设备配置里的 interfaceConfig.interfaces、transfer.from/to，用于坐标提取、对齐、执行参数生成。类型定义在 scene.ts。
    流程层接口 / 工艺流程口：前端 Interface 画布上展示给用户连线的抽象接口，只暴露 Input / Output，不直接暴露设备真实接口。映射逻辑在 interfacePorts.ts。
    连接关系本身存的是 sourceInterface / targetInterface 字符串，当前 UI 会限制为 flow_output -> flow_input，见 InterfacePanel.tsx 和 sceneStore.ts。
    实际上在visual Components中也涉及了这两中接口，还有一种信号传输接口，首先这些接口你要考虑到，然后你要想想这些接口适合在前端实现还是在后端实现？

3.  对于agent的执行，vc_topology_agent_research里的建议我认为很合理，然后基于其中提到的langgraph图状态机，要包含哪些节点内容？编排流程是什么样的，是否需要harness或者looping engineering来做进一步约束？希望你基于实际业务需求来考量，不要一味同意我的话，然后给出决策和理由。

4.  模型实际上只有glb文件，所以如果你说用postgres+minio的话是不是直接开发时本地启动一个supabase即可，redius存储其余必须数据

5.  vc_topology_agent_research.md是一个很好的参考资料，其中关于第四章的拓扑理解 Agent 设计方案中的显示拓扑隐式拓扑，拓扑结构算法以及4.4的内容我都很感兴趣。，这也是我在课题中要考虑到达算法内容，不过这一部分可以以后再做，当前先着重于架构方案设计
