# Visual Components 4.8 工业三维可视化仿真平台 - 文档中心

**项目版本**: v1.0  
**文档更新**: 2026-04  
**开发周期**: 17 周，5 个阶段

---

## 📋 文档概览

本文档中心包含 Visual Components 4.8 对标平台的完整设计方案，涵盖产品定位、技术架构、数据库设计、前后端实现方案以及 AI Agent 仿真系统。

---

## 🎯 项目定位

本平台对标 Visual Components 4.8（工业三维仿真软件），实现为 **Web 原生**的工业车间三维可视化与仿真平台。

### 核心创新

用 **LLM-Agent** 替代 VC 4.8 的手动 Python Script Behavior，实现：
- 自然语言驱动的设备工艺建模
- AI 智能仿真调度
- 零编程门槛的工业仿真

### 与 VC 4.8 的关键差异

| 维度 | VC 4.8 | 本平台 |
|---|---|---|
| 工艺建模 | 手写 Python Script，专家门槛 | 自然语言描述，Agent 自动生成 |
| 仿真调度 | 静态脚本，逻辑与参数耦合 | AI 动态调度，SimPlan 解耦 |
| 协作方式 | 文件传输，单机编辑 | 实时多人协同，云端存储 |
| 部署方式 | Windows 桌面安装包 | Web 浏览器，跨平台，无需安装 |

---

## 📁 文档结构

```
docs/
├── README.md                           # 本文件 - 文档导航
├── product_comparison.md               # 产品对标与颠覆性创新白皮书
│
├── design/                             # 详细设计方案
│   ├── development_plan_llm.md         # 完整开发计划（17周路线图）
│   ├── system_directory_structure.md   # 整体系统目录结构设计
│   ├── development_plan.docx           # 开发计划 Word 版本
│   │
│   ├── frontend/                       # 前端设计
│   │   ├── README.md                   # 前端架构说明
│   │   ├── frontend_design_plan.md     # 前端详细设计方案
│   │   ├── ai_chat_typewriter.ts       # AI 聊天打字机效果实现
│   │   └── properties_panel_update.ts  # 属性面板更新逻辑
│   │
│   ├── backend/                        # 后端设计
│   │   ├── README.md                   # 后端架构说明
│   │   └── backend_design_plan.md      # 后端详细设计方案
│   │
│   ├── database/                       # 数据库设计
│   │   ├── README.md                   # 数据库架构说明
│   │   ├── database_construction_plan.md        # 数据库构建方案
│   │   └── database_layout_supplement.md        # 布局模板补充方案
│   │
│   └── AI/                             # AI Agent 设计
│       ├── README.md                   # AI 架构说明
│       └── ai_simulation_agent_design.md        # AI 仿真 Agent 详细设计
```

---

## 🚀 快速开始

### 1. 了解产品定位
阅读 [product_comparison.md](product_comparison.md) 了解：
- 与 VC 4.8 的功能对标
- 颠覆性创新点
- 支持的设备类型（传送带/机械臂/升降台/仓储柜）

### 2. 查看开发计划
阅读 [design/development_plan_llm.md](design/development_plan_llm.md) 了解：
- 17 周完整开发路线图
- 5 个阶段里程碑
- 技术选型与依赖清单

### 3. 查看系统目录结构
阅读 [design/system_directory_structure.md](design/system_directory_structure.md) 了解：
- 整体代码仓库如何分层
- 前后端、AI、仿真、基础设施如何落目录
- 各阶段优先建设哪些目录

### 4. 深入技术设计
根据需要查看各模块详细设计：
- **前端**: [design/frontend/](design/frontend/)
- **后端**: [design/backend/](design/backend/)
- **数据库**: [design/database/](design/database/)
- **AI Agent**: [design/AI/](design/AI/)

---

## 🏗️ 系统架构概览

```
客户端（Next.js 16 + React Three Fiber）
    │  REST / SSE / WebSocket
    ▼
Nginx（反向代理）
    │
    ▼
FastAPI 主进程
    ├── Scene Router      → MongoDB (scenes)
    ├── Catalog Router    → PostgreSQL + MinIO
    ├── Agent Router      → LangGraph + LLM
    └── Simulation Router → Celery + SimPy
            │
            ▼
    Redis（实时状态 / 任务队列）
            │
            ▼
    Celery Worker（SimPy 仿真）
```

---

## 🛠️ 技术栈

### 前端
- **框架**: Next.js 16.1.6, React 19.2.3
- **3D 引擎**: React Three Fiber 9.5.0, Three.js 0.182.0
- **状态管理**: Zustand 5.0.11
- **UI 组件**: Radix UI, Tailwind CSS 4

### 后端
- **Web 框架**: FastAPI 0.115.0
- **数据库**: PostgreSQL + MongoDB + Redis
- **Agent 框架**: LangGraph 0.2.35
- **仿真引擎**: SimPy 4.1.1
- **任务队列**: Celery 5.4.0

### 存储
- **对象存储**: MinIO 7.2.9
- **缓存**: Redis 7.x

---

## 📊 支持的设备类型

### 1. 传送带（Conveyor）
- 模型格式: GLB
- 参数: 长度/宽度/高度/速度/偏移量
- 仿真算法: continuous_transport

### 2. 机械臂（Robot）
- 模型格式: URDF
- 参数: 6 轴关节配置/速度/限位
- 仿真算法: pick_and_place

### 3. 升降台（Lift）
- 模型格式: GLB
- 参数: XY 双轴运动范围/速度/关键点
- 仿真算法: lift_xy_trajectory

### 4. 仓储柜（Storage）
- 模型格式: GLB
- 参数: 货格配置/分配策略
- 仿真算法: cell_allocation_fifo

---

## 🎯 开发里程碑

| 里程碑 | 时间节点 | 核心产出 |
|---|---|---|
| M1 前端界面可演示 | Week 5 | 全部 UI 组件，Mock 数据驱动 |
| M2 数据库就绪 | Week 8 | Docker 环境，种子数据，前端接真实 API |
| M3 后端 API 完整 | Week 13 | 全部 REST + WebSocket，布局实例化 |
| M4 AI 仿真全链路 | Week 16 | Agent → SimPlan → SimPy → Terminal |
| M5 生产就绪 | Week 17 | 集成测试，Docker 生产配置 |

---

## 📖 详细文档索引

### 产品与规划
- [产品对标白皮书](product_comparison.md) - 功能对标与创新点
- [完整开发计划](design/development_plan_llm.md) - 17 周路线图
- [系统目录结构设计](design/system_directory_structure.md) - 整体仓库分层与阶段映射

### 前端设计
- [前端架构说明](design/frontend/README.md)
- [前端详细设计](design/frontend/frontend_design_plan.md) - 布局/组件/交互
- [AI 聊天打字机](design/frontend/ai_chat_typewriter.ts) - 流式输出实现
- [属性面板更新](design/frontend/properties_panel_update.ts) - 动态表单渲染

### 后端设计
- [后端 / Agent / 数据结构设计索引](backend/README.md) - 最新拆分方案入口
- [后端接口设计](backend/backend_api_design.md) - 设备实例 CRUD、三类连接、接口编译、实时事件
- [Agent Runtime 设计](backend/agent_runtime_design.md) - LangGraph 链路、触发时机、打断恢复、harness
- [数据结构与数据库方案](backend/data_model_database_design.md) - DeviceSpec、SceneDocument、Signal Runtime、Supabase/Redis
- [后端架构说明](design/backend/README.md)
- [后端详细设计](design/backend/backend_design_plan.md) - API/服务/中间件

### 数据库设计
- [数据库架构说明](design/database/README.md)
- [数据库构建方案](design/database/database_construction_plan.md) - PG/Mongo/Redis
- [布局模板方案](design/database/database_layout_supplement.md) - 布局实例化

### AI Agent 设计
- [AI 架构说明](design/AI/README.md)
- [AI 仿真 Agent](design/AI/ai_simulation_agent_design.md) - LangGraph/SimPy

---

## 🔗 相关资源

- **Visual Components 官网**: https://www.visualcomponents.com/
- **LangGraph 文档**: https://langchain-ai.github.io/langgraph/
- **SimPy 文档**: https://simpy.readthedocs.io/
- **React Three Fiber**: https://docs.pmnd.rs/react-three-fiber/

---

## 📝 文档维护

- **创建日期**: 2026-04
- **最后更新**: 2026-04-16
- **维护者**: 开发团队
- **文档版本**: v1.0

---

## ⚠️ 注意事项

1. 本文档基于 Visual Components 4.8 进行对标设计
2. 所有技术方案已考虑实际可行性和性能要求
3. 开发计划为 17 周，分 5 个阶段推进
4. 各模块设计文档相互关联，建议按顺序阅读
