# 前端设计方案

> 工业三维可视化平台 · 对标 VC 4.8 · Next.js 16 + React Three Fiber 9

---

## 一、整体布局结构

```
┌─────────────────────────────────────────────────────────────────────┐
│  TopBar: 菜单栏（工具组 / 操作 / 工具 / 尺寸 / 连接 / 层级 / 导入）  │
├─────────────────────────────────────────────────────────────────────┤
│  SimBar: ▶ ⏸ ⏹  00:00:00  ×1.0  ──────────  📷  📹  ⚙  (透明覆层) │
├──────────────┬──────────────────────────────┬───────────────────────┤
│              │                              │                       │
│   eCatalog   │       3D Viewport            │   Properties Panel    │
│   Panel      │    (React Three Fiber)       │   + AI Chat           │
│   (可调宽)   │       (可调宽)               │   (可调宽)            │
│              │                              │                       │
│  ┌─收藏──┐   │   OrbitControls              │  [坐标] [默认] [Adv]  │
│  │树形目录│  │   GridFloor                  │                       │
│  └───────┘  │   Transform Gizmo            │  ─────────────────    │
│  ┌─预览──┐   │   DeviceMesh × N             │  AI 聊天面板          │
│  │缩略图网格│ │                              │  流式输出             │
│  └───────┘  │                              │                       │
├──────────────┴──────────────────────────────┴───────────────────────┤
│  Terminal Panel (可调高): 布局输出 / SimPy 仿真日志                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、依赖清单（基于 package.json 固定版本）

### 2.1 现有依赖直接使用（不变版本）

```json
{
  "next": "16.1.6",
  "react": "19.2.3",
  "react-dom": "19.2.3",
  "@react-three/fiber": "^9.5.0",
  "@react-three/drei": "^10.7.7",
  "@react-three/postprocessing": "^3.0.4",
  "three": "^0.182.0",
  "@types/three": "^0.182.0",
  "zustand": "^5.0.11",
  "react-resizable-panels": "^4.5.8",
  "lucide-react": "^0.563.0",
  "tailwind-merge": "^3.4.0",
  "clsx": "^2.1.1",
  "class-variance-authority": "^0.7.1",
  "urdf-loader": "^0.12.6",
  "xacro-parser": "^0.3.11"
}
```

### 2.2 需要新增的依赖

```bash
# 拖拽：HTML5 原生增强库（轻量，与 R3F Canvas 兼容最好）
npm install @dnd-kit/core @dnd-kit/utilities

# 虚拟列表：海量设备目录高性能渲染
npm install @tanstack/react-virtual@^3.13.0

# 树形组件：eCatalog 目录树
npm install @radix-ui/react-collapsible @radix-ui/react-scroll-area

# 数字输入：属性面板精确输入
npm install @radix-ui/react-slider @radix-ui/react-select @radix-ui/react-checkbox

# Tabs 组件：属性面板 默认/Advanced/Materials
npm install @radix-ui/react-tabs

# Context Menu：右键菜单（场景中右键设备）
npm install @radix-ui/react-context-menu

# 代码高亮：Terminal 面板日志着色
npm install ansi-to-html

# 分割面板（已有）：react-resizable-panels ^4.5.8
```

> **为什么选 @dnd-kit 而不是 react-dnd？**
> react-dnd 依赖 HTML5 Backend，在 R3F Canvas 内的 three.js 事件系统与原生 DOM 事件系统存在冲突。@dnd-kit 支持指针事件（PointerEvents API），与 R3F 的事件系统可以共存，且 Tree-shaking 友好，包体积更小。

---

## 三、目录结构

```
frontend/
├── app/
│   ├── layout.tsx                    # 根布局
│   ├── page.tsx                      # 根入口：根据登录态跳转到 /login 或 /projects
│   ├── login/
│   │   └── page.tsx                  # 登录页
│   ├── api/
│   │   └── auth/
│   │       └── [...nextauth]/
│   │           └── route.ts          # Auth.js OAuth 入口与回调
│   ├── projects/
│   │   └── page.tsx                  # 项目列表页
│   └── workspace/
│       └── [projectId]/
│           └── page.tsx              # 主工作区页面
│
├── components/
│   ├── layout/
│   │   ├── WorkspaceLayout.tsx       # 五区域分割布局
│   │   ├── TopBar.tsx                # 顶部菜单栏
│   │   └── SimulationBar.tsx         # 仿真控制条（透明覆层）
│   │
│   ├── ecatalog/
│   │   ├── ECatalogPanel.tsx         # eCatalog 容器
│   │   ├── CollectionsTree.tsx       # 左侧目录树（所有模型/公共模型）
│   │   ├── DeviceGrid.tsx            # 右侧缩略图网格（虚拟化）
│   │   ├── DeviceCard.tsx            # 单个设备卡片（可拖拽）
│   │   └── SearchBar.tsx             # 搜索栏
│   │
│   ├── viewport/
│   │   ├── Viewport3D.tsx            # R3F Canvas 容器（接受拖拽 drop）
│   │   ├── SceneContent.tsx          # 场景内容（灯光/地板/设备）
│   │   ├── GridFloor.tsx             # 网格地板
│   │   ├── DeviceInstance.tsx        # 单个设备 Mesh（GLTF/URDF）
│   │   ├── DeviceInstances.tsx       # 设备集合渲染
│   │   ├── TransformGizmo.tsx        # 平移/旋转/缩放控制器
│   │   ├── ConnectionLines.tsx       # 物流连接线
│   │   └── SimulationOverlay.tsx     # 仿真状态覆层
│   │
│   ├── properties/
│   │   ├── PropertiesPanel.tsx       # 属性面板容器
│   │   ├── CoordinateWidget.tsx      # 坐标输入（X/Y/Z + Rx/Ry/Rz）
│   │   ├── DefaultTab.tsx            # 默认 Tab（名称/类别/业务参数）
│   │   ├── AdvancedTab.tsx           # Advanced Tab（结构参数）
│   │   ├── MaterialsTab.tsx          # Materials Tab
│   │   └── fields/
│   │       ├── NumberField.tsx       # 带单位的数字输入
│   │       ├── SelectField.tsx       # 下拉选择
│   │       └── CheckboxField.tsx     # 布尔开关
│   │
│   ├── ai-chat/
│   │   ├── AIChatPanel.tsx           # AI 聊天面板
│   │   ├── MessageList.tsx           # 消息列表
│   │   ├── StreamMessage.tsx         # 流式输出消息气泡
│   │   └── ChatInput.tsx             # 输入框
│   │
│   └── terminal/
│       ├── TerminalPanel.tsx         # 终端面板容器
│       ├── LogLine.tsx               # 单行日志（ANSI 着色）
│       └── useTerminalStream.ts      # WebSocket 日志流 Hook
│
├── stores/
│   ├── sceneStore.ts                 # 场景状态（设备列表/选中/变换）
│   ├── catalogStore.ts              # 目录状态（展开节点/当前集合）
│   ├── simulationStore.ts            # 仿真状态（running/time/speed）
│   └── agentStore.ts                 # AI 对话状态
│
├── hooks/
│   ├── useSceneWebSocket.ts          # 场景实时同步
│   ├── useAgentStream.ts             # AI 流式输出 SSE
│   ├── useGLTFLoader.ts              # 按需加载 GLTF 模型
│   └── useDragToScene.ts             # 拖拽入场逻辑
│
├── lib/
│   ├── auth.ts                       # Auth.js 配置、JWT Session 策略
│   └── auth-providers.ts             # OAuth provider 开关与展示配置
│
└── types/
    ├── scene.ts                      # DeviceInstance / Transform / Connection
    ├── catalog.ts                    # CatalogItem / Category
    ├── agent.ts                      # Message / StreamChunk
    └── next-auth.d.ts                # Session / JWT 类型扩展
```

> 路由职责约定：
> - `/`：认证入口与路由分流页
> - `/login`：本地登录 / OAuth 入口
> - `/api/auth/[...nextauth]`：Auth.js OAuth 发起、回调和会话接口
> - `/projects`：项目列表与最近项目入口
> - `/workspace/[projectId]`：具体项目工作区

---

## 四、核心实现方案

### 4.1 布局系统（react-resizable-panels）

`react-resizable-panels` 支持水平/垂直嵌套分割，完全覆盖 VC 的五区域布局：

```tsx
// components/layout/WorkspaceLayout.tsx
import {
  PanelGroup,
  Panel,
  PanelResizeHandle,
} from "react-resizable-panels";

export function WorkspaceLayout() {
  return (
    <div className="flex flex-col h-screen bg-[#1e1e1e]">
      {/* 顶部菜单栏（固定高度） */}
      <TopBar />

      {/* 主体：三列 + 底部终端 */}
      <PanelGroup direction="vertical" className="flex-1 min-h-0">
        {/* 上方：三列区域 */}
        <Panel defaultSize={75} minSize={40}>
          <PanelGroup direction="horizontal">
            {/* 左：eCatalog */}
            <Panel defaultSize={18} minSize={12} maxSize={30} id="ecatalog">
              <ECatalogPanel />
            </Panel>

            <PanelResizeHandle className="w-[3px] bg-[#333] hover:bg-[#0078d4] transition-colors" />

            {/* 中：3D Viewport */}
            <Panel defaultSize={57} minSize={30} id="viewport">
              <div className="relative h-full">
                {/* 仿真控制条浮在 Canvas 上方 */}
                <SimulationBar className="absolute top-2 left-1/2 -translate-x-1/2 z-10" />
                <Viewport3D />
              </div>
            </Panel>

            <PanelResizeHandle className="w-[3px] bg-[#333] hover:bg-[#0078d4] transition-colors" />

            {/* 右：属性 + AI */}
            <Panel defaultSize={25} minSize={18} maxSize={40} id="properties">
              <PanelGroup direction="vertical">
                <Panel defaultSize={55} minSize={30}>
                  <PropertiesPanel />
                </Panel>
                <PanelResizeHandle className="h-[3px] bg-[#333] hover:bg-[#0078d4] transition-colors" />
                <Panel defaultSize={45} minSize={20}>
                  <AIChatPanel />
                </Panel>
              </PanelGroup>
            </Panel>
          </PanelGroup>
        </Panel>

        <PanelResizeHandle className="h-[3px] bg-[#333] hover:bg-[#0078d4] transition-colors" />

        {/* 下方：终端 */}
        <Panel defaultSize={25} minSize={10} maxSize={50} id="terminal">
          <TerminalPanel />
        </Panel>
      </PanelGroup>
    </div>
  );
}
```

---

### 4.2 eCatalog 实现

#### 4.2.1 目录树（CollectionsTree）

目录结构：
```
所有模型
公共模型
  └── 部件 (Components)
  └── 布局 (Layouts)
我的模型
当前打开
最近模型
最常使用的
按类型的模型
按制造商的模型
```

使用 `@radix-ui/react-collapsible` 实现折叠树：

```tsx
// components/ecatalog/CollectionsTree.tsx
import * as Collapsible from "@radix-ui/react-collapsible";
import { ChevronRight, Folder, FolderOpen } from "lucide-react";
import { useCatalogStore } from "@/stores/catalogStore";

const TREE_DATA = [
  { id: "all", label: "所有模型", icon: "star", children: [] },
  {
    id: "public",
    label: "公共模型",
    children: [
      { id: "components", label: "Components", children: [] },
      { id: "layouts", label: "Layouts", children: [] },
    ],
  },
  { id: "mine", label: "我的模型", children: [] },
  { id: "open", label: "当前打开", children: [] },
  { id: "recent", label: "最近模型", children: [] },
  { id: "favorites", label: "最常使用的", children: [] },
  { id: "byType", label: "按类型的模型", children: [] },
  { id: "byMfr", label: "按制造商的模型", children: [] },
];

function TreeNode({ node, depth = 0 }) {
  const { selectedCollection, setSelectedCollection, expandedNodes, toggleNode } =
    useCatalogStore();
  const isExpanded = expandedNodes.has(node.id);
  const isSelected = selectedCollection === node.id;
  const hasChildren = node.children?.length > 0;

  return (
    <Collapsible.Root open={isExpanded} onOpenChange={() => toggleNode(node.id)}>
      <div
        className={`flex items-center gap-1 py-[3px] px-2 cursor-pointer text-sm
          rounded-sm select-none
          ${isSelected ? "bg-[#0078d4] text-white" : "text-[#cccccc] hover:bg-[#2a2a2a]"}`}
        style={{ paddingLeft: `${8 + depth * 16}px` }}
        onClick={() => setSelectedCollection(node.id)}
      >
        {hasChildren ? (
          <Collapsible.Trigger asChild>
            <ChevronRight
              size={12}
              className={`transition-transform shrink-0 ${isExpanded ? "rotate-90" : ""}`}
              onClick={(e) => e.stopPropagation()}
            />
          </Collapsible.Trigger>
        ) : (
          <span className="w-3" />
        )}
        {isExpanded ? (
          <FolderOpen size={14} className="shrink-0 text-[#e8c56d]" />
        ) : (
          <Folder size={14} className="shrink-0 text-[#e8c56d]" />
        )}
        <span className="truncate">{node.label}</span>
      </div>
      {hasChildren && (
        <Collapsible.Content>
          {node.children.map((child) => (
            <TreeNode key={child.id} node={child} depth={depth + 1} />
          ))}
        </Collapsible.Content>
      )}
    </Collapsible.Root>
  );
}
```

#### 4.2.2 设备预览网格（虚拟化渲染）

当设备数量超过 500 时，DOM 节点过多导致卡顿。使用 `@tanstack/react-virtual` 实现只渲染可视区域内的卡片：

```tsx
// components/ecatalog/DeviceGrid.tsx
import { useVirtualizer } from "@tanstack/react-virtual";
import { useRef } from "react";
import { DeviceCard } from "./DeviceCard";

// 两列网格虚拟化
export function DeviceGrid({ items }: { items: CatalogItem[] }) {
  const parentRef = useRef<HTMLDivElement>(null);

  // 将数据按两列分组
  const rows = [];
  for (let i = 0; i < items.length; i += 2) {
    rows.push(items.slice(i, i + 2));
  }

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 120,        // 每行预估高度 px
    overscan: 5,                    // 超出可视区预渲染行数
  });

  return (
    <div ref={parentRef} className="overflow-y-auto flex-1 p-2">
      <div style={{ height: `${virtualizer.getTotalSize()}px`, position: "relative" }}>
        {virtualizer.getVirtualItems().map((virtualRow) => (
          <div
            key={virtualRow.index}
            style={{
              position: "absolute",
              top: virtualRow.start,
              left: 0,
              right: 0,
              height: virtualRow.size,
            }}
            className="flex gap-2"
          >
            {rows[virtualRow.index].map((item) => (
              <DeviceCard key={item.id} item={item} />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

### 4.3 拖拽入场（eCatalog → 3D Viewport）

**实现原理：** HTML5 原生 drag + R3F Canvas 的 `onDrop`，通过 Raycasting 将屏幕坐标转为世界坐标。

**为什么不用 @dnd-kit 的 droppable 覆盖 Canvas？**
因为 R3F 的 Canvas 本质是一个 `<canvas>` DOM 元素，@dnd-kit 的 Droppable 需要 DOM 感知才能计算边界。最干净的方案是：HTML5 Drag 负责"传递数据"，Canvas 的 `onDrop` 负责"接收位置"，Raycasting 负责"转换坐标"。

```tsx
// components/ecatalog/DeviceCard.tsx
export function DeviceCard({ item }: { item: CatalogItem }) {
  const handleDragStart = (e: React.DragEvent) => {
    // 将设备 ID 写入 dataTransfer，供 Canvas 接收
    e.dataTransfer.setData("application/device-id", item.id);
    e.dataTransfer.setData("application/device-category", item.category);
    e.dataTransfer.effectAllowed = "copy";
  };

  return (
    <div
      draggable
      onDragStart={handleDragStart}
      className="w-[calc(50%-4px)] aspect-square bg-[#2d2d2d] rounded
        border border-[#3a3a3a] hover:border-[#0078d4] cursor-grab
        active:cursor-grabbing flex flex-col items-center p-1 gap-1
        transition-colors select-none"
    >
      {/* 预览图 */}
      <img
        src={item.thumbnailUrl}
        alt={item.name}
        className="w-full flex-1 object-contain"
        draggable={false}
      />
      <span className="text-[10px] text-[#aaa] text-center truncate w-full px-1">
        {item.name}
      </span>
    </div>
  );
}
```

```tsx
// components/viewport/Viewport3D.tsx
import { Canvas, useThree } from "@react-three/fiber";
import { useSceneStore } from "@/stores/sceneStore";
import * as THREE from "three";

// 内部组件：处理 drop 后的 Raycasting
function DropHandler({ onDrop }: { onDrop: (position: THREE.Vector3, deviceId: string) => void }) {
  const { camera, gl, scene } = useThree();

  const handleCanvasDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const deviceId = e.dataTransfer.getData("application/device-id");
    if (!deviceId) return;

    // 计算 NDC 坐标
    const rect = gl.domElement.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    const y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    // Raycasting：与地板平面相交，获取世界坐标
    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera({ x, y }, camera);
    const floorPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
    const worldPos = new THREE.Vector3();
    raycaster.ray.intersectPlane(floorPlane, worldPos);

    onDrop(worldPos, deviceId);
  };

  // 将事件绑定到 canvas DOM
  React.useEffect(() => {
    const canvas = gl.domElement;
    const preventDefault = (e: DragEvent) => e.preventDefault();
    canvas.addEventListener("dragover", preventDefault);
    return () => canvas.removeEventListener("dragover", preventDefault);
  }, [gl]);

  return null; // 纯逻辑组件
}

export function Viewport3D() {
  const { addDevice } = useSceneStore();

  const handleDrop = (position: THREE.Vector3, deviceId: string) => {
    addDevice({
      catalogId: deviceId,
      transform: {
        position: [position.x, 0, position.z], // y 固定为 0（地面）
        rotation: [0, 0, 0],
        scale: [1, 1, 1],
      },
    });
  };

  return (
    <div
      className="w-full h-full"
      onDragOver={(e) => e.preventDefault()}
    >
      <Canvas
        camera={{ position: [10, 10, 10], fov: 45 }}
        shadows
        gl={{ antialias: true }}
      >
        <DropHandler onDrop={handleDrop} />
        <SceneContent />
      </Canvas>
    </div>
  );
}
```

---

### 4.4 GLTF / URDF 模型加载与实例化渲染

```tsx
// components/viewport/DeviceInstance.tsx
import { useGLTF } from "@react-three/drei";
import { useEffect, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

export function DeviceInstance({ instance, isSelected, onClick }) {
  const { scene } = useGLTF(instance.modelUrl);  // drei 内置缓存，相同 URL 只加载一次
  const groupRef = useRef<THREE.Group>(null);
  const cloned = useMemo(() => scene.clone(true), [scene]);

  // 选中时高亮（替换 emissive）
  useEffect(() => {
    cloned.traverse((child) => {
      if (child instanceof THREE.Mesh) {
        child.material = child.material.clone();
        child.material.emissive.set(isSelected ? "#1a4a6e" : "#000000");
        child.material.emissiveIntensity = isSelected ? 0.3 : 0;
      }
    });
  }, [isSelected, cloned]);

  return (
    <group
      ref={groupRef}
      position={instance.transform.position}
      rotation={instance.transform.rotation}
      scale={instance.transform.scale}
      onClick={(e) => { e.stopPropagation(); onClick(instance.instanceId); }}
    >
      <primitive object={cloned} />
      {/* 选中时显示包围盒 */}
      {isSelected && <SelectionBox target={cloned} />}
    </group>
  );
}

// URDF 支持（使用 urdf-loader）
export function URDFDeviceInstance({ instance, isSelected, onClick }) {
  const groupRef = useRef<THREE.Group>(null);

  useEffect(() => {
    const loader = new URDFLoader();
    loader.load(instance.modelUrl, (robot) => {
      groupRef.current?.add(robot);
    });
  }, [instance.modelUrl]);

  return (
    <group ref={groupRef}
      position={instance.transform.position}
      onClick={(e) => { e.stopPropagation(); onClick(instance.instanceId); }}
    />
  );
}
```

---

### 4.5 属性面板（Properties Panel）

#### 坐标 Widget

对标 VC 4.8 的世界/父/本地坐标切换：

```tsx
// components/properties/CoordinateWidget.tsx
import * as Tabs from "@radix-ui/react-tabs";

export function CoordinateWidget({ transform, onChange }) {
  const [coordMode, setCoordMode] = useState<"world" | "parent" | "local">("world");

  return (
    <div className="p-3 border-b border-[#333]">
      {/* 坐标系切换 */}
      <div className="flex gap-2 mb-3">
        {(["world", "parent", "local"] as const).map((mode) => (
          <button key={mode}
            onClick={() => setCoordMode(mode)}
            className={`px-2 py-0.5 text-xs rounded
              ${coordMode === mode ? "bg-[#0078d4] text-white" : "bg-[#2d2d2d] text-[#aaa]"}`}
          >
            {mode === "world" ? "世界" : mode === "parent" ? "父座标" : "物体"}
          </button>
        ))}
      </div>

      {/* XYZ 位置 */}
      <div className="grid grid-cols-3 gap-1 mb-2">
        {["X", "Y", "Z"].map((axis, i) => (
          <div key={axis} className="flex items-center gap-1">
            <span className={`text-xs font-bold w-3
              ${axis === "X" ? "text-[#e06c75]" : axis === "Y" ? "text-[#98c379]" : "text-[#61afef]"}`}>
              {axis}
            </span>
            <input
              type="number"
              value={transform.position[i].toFixed(3)}
              onChange={(e) => {
                const pos = [...transform.position];
                pos[i] = parseFloat(e.target.value);
                onChange({ ...transform, position: pos });
              }}
              className="flex-1 bg-[#1a1a1a] border border-[#444] rounded px-1 py-0.5
                text-xs text-[#ddd] text-right outline-none focus:border-[#0078d4]"
              step="0.001"
            />
          </div>
        ))}
      </div>

      {/* Rx Ry Rz 旋转 */}
      <div className="grid grid-cols-3 gap-1">
        {["Rx", "Ry", "Rz"].map((axis, i) => (
          <div key={axis} className="flex items-center gap-1">
            <span className="text-xs text-[#888] w-5">{axis}</span>
            <input
              type="number"
              value={((transform.rotation[i] * 180) / Math.PI).toFixed(1)}
              onChange={(e) => {
                const rot = [...transform.rotation];
                rot[i] = (parseFloat(e.target.value) * Math.PI) / 180;
                onChange({ ...transform, rotation: rot });
              }}
              className="flex-1 bg-[#1a1a1a] border border-[#444] rounded px-1 py-0.5
                text-xs text-[#ddd] text-right outline-none focus:border-[#0078d4]"
              step="1"
            />
          </div>
        ))}
      </div>
    </div>
  );
}
```

#### 动态参数表单（由 device_spec.schema_json 驱动）

属性面板的"默认"和"Advanced" Tab 中的参数字段，完全由后端返回的 `schema_json` 动态渲染，无需前端硬编码：

```tsx
// components/properties/DefaultTab.tsx
// schema_json 示例结构（后端返回）：
// {
//   "default": [
//     { "key": "名称", "field": "name", "type": "string" },
//     { "key": "类别", "field": "category", "type": "string", "readonly": true },
//     { "key": "ConveyorLength", "field": "conveyor_length", "type": "number", "unit": "mm" },
//     { "key": "ConveyorSpeed",  "field": "conveyor_speed",  "type": "number", "unit": "mm/s" },
//     { "key": "ShowSupport",    "field": "show_support",    "type": "boolean" }
//   ],
//   "advanced": [ ... ]
// }

export function DynamicParamForm({ schema, values, onChange }) {
  return (
    <div className="space-y-1 p-3">
      {schema.map((field) => (
        <div key={field.field} className="flex items-center justify-between py-1
          border-b border-[#2a2a2a] last:border-0">
          <span className="text-xs text-[#999] w-32 shrink-0">{field.key}</span>
          <FieldRenderer field={field} value={values[field.field]} onChange={onChange} />
        </div>
      ))}
    </div>
  );
}

function FieldRenderer({ field, value, onChange }) {
  if (field.type === "boolean") {
    return (
      <input type="checkbox" checked={!!value}
        onChange={(e) => onChange(field.field, e.target.checked)}
        className="accent-[#0078d4]" />
    );
  }
  if (field.type === "select") {
    return (
      <select value={value}
        onChange={(e) => onChange(field.field, e.target.value)}
        className="bg-[#1a1a1a] border border-[#444] rounded px-1 py-0.5 text-xs text-[#ddd]">
        {field.options.map((opt) => <option key={opt}>{opt}</option>)}
      </select>
    );
  }
  // 默认 number / string
  return (
    <div className="flex items-center gap-1">
      <input type={field.type === "number" ? "number" : "text"}
        value={value ?? ""}
        readOnly={field.readonly}
        onChange={(e) => onChange(field.field, field.type === "number"
          ? parseFloat(e.target.value) : e.target.value)}
        className="w-24 bg-[#1a1a1a] border border-[#444] rounded px-1 py-0.5
          text-xs text-[#ddd] text-right outline-none focus:border-[#0078d4]
          read-only:opacity-50 read-only:cursor-not-allowed"
      />
      {field.unit && <span className="text-[10px] text-[#666] w-8">{field.unit}</span>}
    </div>
  );
}
```

---

### 4.6 AI 聊天面板 + LLM 流式输出

#### 流式输出原理（SSE）

后端 FastAPI 返回 `text/event-stream`，前端用 `fetch` + `ReadableStream` 逐 token 消费，**不使用** `EventSource`（EventSource 不支持 POST 请求）：

```tsx
// hooks/useAgentStream.ts
import { useAgentStore } from "@/stores/agentStore";

export function useAgentStream() {
  const { addMessage, appendToLastMessage, setStreaming } = useAgentStore();

  const sendMessage = async (sessionId: string, content: string) => {
    // 立即添加用户消息
    addMessage({ role: "user", content });
    // 添加空的 AI 消息占位
    addMessage({ role: "assistant", content: "", streaming: true });
    setStreaming(true);

    try {
      const response = await fetch(`/api/agent/sessions/${sessionId}/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });

      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      // 逐 chunk 读取
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        // SSE 格式：每行 "data: {token}\n\n"
        const lines = chunk.split("\n");
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const token = line.slice(6);
            if (token === "[DONE]") break;
            appendToLastMessage(token); // 追加 token 到最后一条消息
          }
        }
      }
    } finally {
      setStreaming(false);
    }
  };

  return { sendMessage };
}
```

```tsx
// components/ai-chat/StreamMessage.tsx
import { useEffect, useRef } from "react";

export function StreamMessage({ message }) {
  const cursorRef = useRef<HTMLSpanElement>(null);

  // 流式输出时的闪烁光标
  return (
    <div className={`flex gap-2 ${message.role === "user" ? "flex-row-reverse" : ""}`}>
      <div className={`max-w-[85%] rounded-lg px-3 py-2 text-sm
        ${message.role === "user"
          ? "bg-[#0078d4] text-white ml-auto"
          : "bg-[#2d2d2d] text-[#ddd]"}`}>
        <pre className="whitespace-pre-wrap font-sans">{message.content}</pre>
        {message.streaming && (
          <span className="inline-block w-[2px] h-[14px] bg-[#0078d4] ml-0.5
            animate-pulse align-middle" />
        )}
      </div>
    </div>
  );
}
```

---

### 4.7 终端面板

支持 ANSI 颜色码渲染（SimPy 日志通常带颜色）和自动滚底：

```tsx
// components/terminal/TerminalPanel.tsx
import { useEffect, useRef, useCallback } from "react";
import { useTerminalStream } from "./useTerminalStream";
import convert from "ansi-to-html"; // npm: ansi-to-html

const converter = new convert({ escapeXML: true });

export function TerminalPanel() {
  const { logs, clear } = useTerminalStream();
  const bottomRef = useRef<HTMLDivElement>(null);

  // 新日志时自动滚底
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs.length]);

  return (
    <div className="flex flex-col h-full bg-[#0d0d0d] border-t border-[#333]">
      {/* 头部 */}
      <div className="flex items-center justify-between px-3 py-1
        border-b border-[#222] bg-[#161616]">
        <span className="text-xs text-[#888] font-mono">输出</span>
        <button onClick={clear}
          className="text-[10px] text-[#555] hover:text-[#999] transition-colors">
          清除
        </button>
      </div>

      {/* 日志区域 */}
      <div className="flex-1 overflow-y-auto font-mono text-xs leading-5 p-2 space-y-0.5">
        {logs.map((log, i) => (
          <div key={i}
            className="text-[#cccccc] whitespace-pre-wrap"
            dangerouslySetInnerHTML={{
              __html: converter.toHtml(log.text),
            }}
          />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
```

```tsx
// components/terminal/useTerminalStream.ts
import { useEffect } from "react";
import { useSimulationStore } from "@/stores/simulationStore";

export function useTerminalStream() {
  const { logs, addLog, clearLogs } = useSimulationStore();

  useEffect(() => {
    // WebSocket 接收后端布局加载和仿真日志
    const ws = new WebSocket(`ws://localhost:8000/ws/terminal`);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      addLog({ text: data.text, level: data.level, timestamp: Date.now() });
    };

    return () => ws.close();
  }, []);

  return { logs, clear: clearLogs };
}
```

---

### 4.8 仿真控制条（SimulationBar）

浮于 3D Viewport 上方，半透明背景，对标 VC 4.8 的仿真控制区：

```tsx
// components/layout/SimulationBar.tsx
import { Play, Pause, Square, SkipBack } from "lucide-react";
import { useSimulationStore } from "@/stores/simulationStore";

export function SimulationBar({ className }: { className?: string }) {
  const { running, simTime, speed, start, pause, stop, setSpeed } =
    useSimulationStore();

  const formatTime = (seconds: number) => {
    const h = Math.floor(seconds / 3600).toString().padStart(2, "0");
    const m = Math.floor((seconds % 3600) / 60).toString().padStart(2, "0");
    const s = Math.floor(seconds % 60).toString().padStart(2, "0");
    return `${h}:${m}:${s}`;
  };

  return (
    <div className={`flex items-center gap-3 px-4 py-1.5
      bg-[#1e1e1e]/80 backdrop-blur-sm rounded-lg border border-[#444]/50
      shadow-lg ${className}`}>

      {/* 重置 */}
      <button onClick={stop}
        className="text-[#888] hover:text-[#ddd] transition-colors">
        <SkipBack size={14} />
      </button>

      {/* 播放/暂停 */}
      <button
        onClick={running ? pause : start}
        className="w-6 h-6 rounded-full bg-[#0078d4] hover:bg-[#1184db]
          flex items-center justify-center transition-colors">
        {running
          ? <Pause size={10} className="text-white" />
          : <Play size={10} className="text-white ml-0.5" />}
      </button>

      {/* 停止 */}
      <button onClick={stop}
        className="text-[#888] hover:text-[#ddd] transition-colors">
        <Square size={14} />
      </button>

      {/* 时间显示 */}
      <span className="font-mono text-xs text-[#cccc00] min-w-[60px] text-center">
        {formatTime(simTime)}
      </span>

      {/* 速度控制 */}
      <div className="flex items-center gap-1">
        <span className="text-xs text-[#888]">×</span>
        <select
          value={speed}
          onChange={(e) => setSpeed(parseFloat(e.target.value))}
          className="bg-transparent text-xs text-[#ccc] border-none outline-none cursor-pointer">
          {[0.1, 0.5, 1.0, 2.0, 5.0, 10.0].map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>
    </div>
  );
}
```

---

## 五、Zustand Store 设计

```ts
// stores/sceneStore.ts
import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import type { DeviceInstance, Transform } from "@/types/scene";

interface SceneState {
  devices: DeviceInstance[];
  selectedId: string | null;
  // Actions
  addDevice: (payload: { catalogId: string; transform: Transform }) => void;
  removeDevice: (instanceId: string) => void;
  updateTransform: (instanceId: string, transform: Partial<Transform>) => void;
  updateProcessConfig: (instanceId: string, config: Record<string, unknown>) => void;
  selectDevice: (instanceId: string | null) => void;
}

export const useSceneStore = create<SceneState>()(
  immer((set) => ({
    devices: [],
    selectedId: null,

    addDevice: (payload) => set((state) => {
      state.devices.push({
        instanceId: crypto.randomUUID(),
        catalogId: payload.catalogId,
        transform: payload.transform,
        processConfig: {},
        name: `Device-${state.devices.length + 1}`,
      });
    }),

    removeDevice: (instanceId) => set((state) => {
      state.devices = state.devices.filter((d) => d.instanceId !== instanceId);
    }),

    updateTransform: (instanceId, transform) => set((state) => {
      const device = state.devices.find((d) => d.instanceId === instanceId);
      if (device) Object.assign(device.transform, transform);
    }),

    updateProcessConfig: (instanceId, config) => set((state) => {
      const device = state.devices.find((d) => d.instanceId === instanceId);
      if (device) Object.assign(device.processConfig, config);
    }),

    selectDevice: (id) => set((state) => { state.selectedId = id; }),
  }))
);
```

---

## 六、颜色/主题规范

对标 VC 4.8 深色工业风（在 `tailwind.config.ts` 或 CSS 变量中定义）：

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

## 七、开发顺序建议

1. **WorkspaceLayout** → 五区域分割骨架（1 天）
2. **eCatalog 树 + 静态网格** → 先用假数据 + 虚拟化（2 天）
3. **R3F Viewport** → 地板 + 轨道控制 + 灯光（1 天）
4. **拖拽入场** → DeviceCard drag + Canvas drop + Raycasting（2 天）
5. **CoordinateWidget + DynamicParamForm** → 属性面板（2 天）
6. **TerminalPanel + WebSocket** → 日志流（1 天）
7. **AIChatPanel + SSE 流式输出** → AI 聊天（2 天）
8. **SimulationBar + 仿真状态联动** → 控制条（1 天）
