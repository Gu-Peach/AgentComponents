# 前端架构设计

> Next.js 16 + React Three Fiber 9 + Zustand 5
> 对标 Visual Components 4.8 深色工业风格

---

## 📋 目录结构

```
frontend/
├── app/
│   ├── layout.tsx                    # 根布局
│   ├── page.tsx                      # 重定向到 /workspace
│   └── workspace/[projectId]/
│       └── page.tsx                  # 主工作区页面
│
├── components/
│   ├── layout/                       # 布局组件
│   │   ├── WorkspaceLayout.tsx       # 五区域分割布局
│   │   ├── TopBar.tsx                # 顶部菜单栏
│   │   └── SimulationBar.tsx         # 仿真控制条（透明覆层）
│   │
│   ├── ecatalog/                     # 电子目录
│   │   ├── ECatalogPanel.tsx         # 目录容器
│   │   ├── CollectionsTree.tsx       # 目录树（折叠）
│   │   ├── DeviceGrid.tsx            # 设备网格（虚拟化）
│   │   ├── DeviceCard.tsx            # 设备卡片（可拖拽）
│   │   └── SearchBar.tsx             # 搜索栏
│   │
│   ├── viewport/                     # 3D 视口
│   │   ├── Viewport3D.tsx            # R3F Canvas 容器
│   │   ├── SceneContent.tsx          # 场景内容
│   │   ├── GridFloor.tsx             # 网格地板
│   │   ├── DeviceInstance.tsx        # 单个设备 Mesh
│   │   ├── DeviceInstances.tsx       # 设备集合渲染
│   │   ├── TransformGizmo.tsx        # 变换控制器
│   │   └── ConnectionLines.tsx       # 物流连接线
│   │
│   ├── properties/                   # 属性面板
│   │   ├── PropertiesPanel.tsx       # 属性面板容器
│   │   ├── CoordinateWidget.tsx      # 坐标输入
│   │   ├── tabs/
│   │   │   ├── DefaultTab.tsx        # 默认 Tab
│   │   │   └── SimulationTab.tsx     # 仿真 Tab
│   │   └── fields/
│   │       ├── PropRowText.tsx       # 文本字段
│   │       ├── PropRowNumber.tsx     # 数字字段（带单位）
│   │       └── PropRowSelect.tsx     # 下拉选择
│   │
│   ├── ai-chat/                      # AI 聊天
│   │   ├── AIChatPanel.tsx           # 聊天面板
│   │   ├── MessageList.tsx           # 消息列表
│   │   ├── StreamMessage.tsx         # 流式消息（打字机）
│   │   └── ChatInput.tsx             # 输入框
│   │
│   └── terminal/                     # 终端面板
│       ├── TerminalPanel.tsx         # 终端容器
│       ├── LogLine.tsx               # 单行日志（ANSI 着色）
│       └── useTerminalStream.ts      # WebSocket 日志流
│
├── stores/                           # Zustand 状态管理
│   ├── sceneStore.ts                 # 场景状态
│   ├── catalogStore.ts               # 目录状态
│   ├── simulationStore.ts            # 仿真状态
│   └── agentStore.ts                 # AI 对话状态
│
├── hooks/                            # 自定义 Hooks
│   ├── useTypewriter.ts              # RAF 打字机效果
│   ├── useAgentStream.ts             # SSE 流式输出
│   ├── useSceneWebSocket.ts          # 场景实时同步
│   ├── useGLTFLoader.ts              # GLTF 模型加载
│   └── useDragToScene.ts             # 拖拽入场逻辑
│
└── types/                            # TypeScript 类型定义
    ├── scene.ts                      # 场景相关类型
    ├── catalog.ts                    # 目录相关类型
    └── agent.ts                      # Agent 相关类型
```

---

## 🎨 布局结构

```
┌─────────────────────────────────────────────────────────────────┐
│  TopBar: 菜单栏（工具组 / 操作 / 工具 / 尺寸 / 连接 / 层级）    │
├─────────────────────────────────────────────────────────────────┤
│  SimBar: ▶ ⏸ ⏹  00:00:00  ×1.0  (透明覆层)                     │
├──────────────┬──────────────────────────────┬───────────────────┤
│              │                              │                   │
│  eCatalog    │       3D Viewport            │  Properties Panel │
│  Panel       │    (React Three Fiber)       │  + AI Chat        │
│  (可调宽)    │       (可调宽)               │  (可调宽)         │
│              │                              │                   │
│  ┌─收藏──┐   │   OrbitControls              │  [坐标] [默认]    │
│  │树形目录│   │   GridFloor                  │  [仿真]           │
│  └───────┘   │   Transform Gizmo            │                   │
│  ┌─预览──┐   │   DeviceMesh × N             │  ─────────────    │
│  │缩略图网格│ │                              │  AI 聊天面板      │
│  └───────┘   │                              │  流式输出         │
├──────────────┴──────────────────────────────┴───────────────────┤
│  Terminal Panel (可调高): 布局输出 / SimPy 仿真日志             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔧 核心技术实现

### 1. 五区域分割布局

使用 `react-resizable-panels` 实现任意调整的五区域布局：

```tsx
<PanelGroup direction="vertical">
  <Panel defaultSize={75}>
    <PanelGroup direction="horizontal">
      <Panel defaultSize={18} minSize={12} maxSize={30}>
        <ECatalogPanel />
      </Panel>
      <PanelResizeHandle />
      <Panel defaultSize={57} minSize={30}>
        <Viewport3D />
      </Panel>
      <PanelResizeHandle />
      <Panel defaultSize={25} minSize={18} maxSize={40}>
        <PropertiesPanel />
        <AIChatPanel />
      </Panel>
    </PanelGroup>
  </Panel>
  <PanelResizeHandle />
  <Panel defaultSize={25}>
    <TerminalPanel />
  </Panel>
</PanelGroup>
```

### 2. 拖拽入场实现

**技术方案**: HTML5 原生 drag + Canvas onDrop + Raycasting

```tsx
// DeviceCard: 设置 draggable，传递 deviceId
const handleDragStart = (e: React.DragEvent) => {
  e.dataTransfer.setData("application/device-id", item.id);
  e.dataTransfer.effectAllowed = "copy";
};

// Viewport3D: Canvas onDrop 接收，Raycasting 转世界坐标
const handleCanvasDrop = (e: DragEvent) => {
  const deviceId = e.dataTransfer.getData("application/device-id");
  const rect = gl.domElement.getBoundingClientRect();
  const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
  const y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
  
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera({ x, y }, camera);
  const floorPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  const worldPos = new THREE.Vector3();
  raycaster.ray.intersectPlane(floorPlane, worldPos);
  
  addDevice({ catalogId: deviceId, transform: { position: [worldPos.x, 0, worldPos.z] } });
};
```

### 3. 虚拟化渲染

使用 `@tanstack/react-virtual` 实现大目录高性能渲染：

```tsx
const virtualizer = useVirtualizer({
  count: rows.length,
  getScrollElement: () => parentRef.current,
  estimateSize: () => 120,
  overscan: 5,
});
```

### 4. AI 聊天打字机效果

**核心原理**: SSE 累积完整文本 → RAF 动画逐步显示

```tsx
// useTypewriter.ts
// 增量续打判断：target.startsWith(current) → 从断点继续
// 否则清空重打

// useAgentStream.ts
// fetch + ReadableStream，按行解析 SSE
// 累积 token 到 accumulated，更新 store
```

### 5. 属性面板动态渲染

四类设备各自的参数字段由后端 `device_specs` 驱动，前端无硬编码：

- **Conveyor**: ConveyorLength / Width / Height / Speed / LiftOffset
- **Robot**: speed + 6 轴关节折叠列表
- **Lift**: rootAxis / carrierAxis / rootRange / carrierRange / speed
- **Storage**: 货格卡片网格（XYZ 可编辑，支持增删）

---

## 🎨 颜色系统

对标 VC 4.8 深色工业风：

```css
:root {
  --bg-base:       #1e1e1e;   /* 主背景 */
  --bg-panel:      #252526;   /* 面板背景 */
  --bg-item:       #2d2d2d;   /* 列表项背景 */
  --bg-hover:      #2a2d2e;   /* hover 背景 */
  --bg-selected:   #0078d4;   /* 选中蓝 */
  --bg-input:      #1a1a1a;   /* 输入框背景 */

  --border-base:   #333333;
  --border-focus:  #0078d4;

  --text-primary:  #cccccc;
  --text-secondary:#888888;
  --text-disabled: #555555;

  --accent-blue:   #0078d4;
  --accent-yellow: #cccc00;   /* 仿真时间显示 */
  --axis-x:        #e06c75;
  --axis-y:        #98c379;
  --axis-z:        #61afef;

  --folder-icon:   #e8c56d;
}
```

---

## 📦 核心依赖

```json
{
  "next": "16.1.6",
  "react": "19.2.3",
  "@react-three/fiber": "^9.5.0",
  "@react-three/drei": "^10.7.7",
  "three": "^0.182.0",
  "zustand": "^5.0.11",
  "react-resizable-panels": "^4.5.8",
  "urdf-loader": "^0.12.6",
  "@tanstack/react-virtual": "^3.13.0",
  "@radix-ui/react-tabs": "latest",
  "@radix-ui/react-collapsible": "latest",
  "ansi-to-html": "latest"
}
```

---

## 🚀 开发顺序

### Week 1: 工程初始化 + 布局骨架
- Next.js 16 + TypeScript + Tailwind CSS 4
- react-resizable-panels 五区域布局
- Zustand store 骨架

### Week 2: eCatalog 面板
- CollectionsTree 折叠树
- DeviceGrid 虚拟化网格
- DeviceCard 拖拽

### Week 3: 3D Viewport 基础
- React Three Fiber Canvas
- GridFloor + OrbitControls
- 拖拽入场 + Raycasting

### Week 4: 属性面板 + 仿真控制条
- CoordinateWidget
- DefaultTab + SimulationTab
- SimulationBar 浮层

### Week 5: AI 聊天 + 终端面板
- AIChatPanel + 打字机效果
- TerminalPanel + ANSI 着色
- 整体联调

---

## 📖 详细文档

- [前端详细设计方案](frontend_design_plan.md) - 完整技术实现
- [AI 聊天打字机](ai_chat_typewriter.ts) - 流式输出实现
- [属性面板更新](properties_panel_update.ts) - 动态表单渲染

---

## 🔗 相关资源

- **React Three Fiber**: https://docs.pmnd.rs/react-three-fiber/
- **Zustand**: https://zustand-demo.pmnd.rs/
- **Radix UI**: https://www.radix-ui.com/
- **Tailwind CSS**: https://tailwindcss.com/
