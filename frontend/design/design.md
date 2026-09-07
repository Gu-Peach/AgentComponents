# Frontend 初版设计与实现归档

更新时间：2026-09-07  
阶段：基础界面、交互框架、三维场景承载能力  
范围：仅实现前端工作区基础能力，不引入 Agent、复杂仿真调度、登录权限或真实实时状态同步。

---

## 1. 本阶段目标

当前前端目标是先建立一个可运行、可交互、可扩展的 VC 风格三维工作区，为后续接入后端 `DeviceSpec / SceneDocument / SceneBehaviorGraph / RuntimeSnapshot` 打基础。

本阶段已经实现：

| 区域 | 实现内容 |
|---|---|
| Header 顶部栏 | 项目名称、工具按钮占位、用户头像占位、顶部栏收缩。 |
| 左侧设备资产库 | 设备模型 / 场景模型分类、搜索过滤、选中状态、双击/加号添加到场景、拖拽数据传递。 |
| 中间三维场景 | React Three Fiber Canvas、相机、灯光、网格地面、坐标轴、mock 设备模型、对象选中高亮。 |
| 右侧属性面板 | 展示并编辑选中对象名称、类型、描述、坐标位置、旋转角度、实例来源和 ID。 |
| Footer 终端输出 | 本地日志流、操作日志追加、日志清空、底部面板收缩。 |
| 面板交互 | Header / 左侧 / 右侧 / Footer 均可收缩；左右面板和底部面板支持拖拽调整尺寸。 |

---

## 2. 技术栈选择

### 2.1 Next + Vite 组合评估

用户初步设定为 `Next.js + React + TypeScript`，并结合 Vite 生态能力构建前端工程。当前项目内没有已有前端工程规范，也没有强制要求 Next 与 Vite 同时作为构建器运行。

结论：**页面应用采用 Next.js 标准构建方案，不把 Vite 作为应用打包器叠加进来；Vite 生态仅用于 Vitest 单元/组件测试。**

原因：

- Next.js 已自带路由、SSR/SSG、Turbopack 构建和生产打包能力；再叠 Vite 作为页面构建器会产生双构建链路、别名解析和 dev server 边界问题。
- 当前阶段目标是基础工作区，不需要独立 Vite 微前端或纯客户端单页构建。
- Vite 生态最适合保留在测试侧：`vitest` 启动快，适合验证 store、组件交互和纯前端逻辑。

当前采用：

| 类型 | 技术 |
|---|---|
| 应用框架 | Next.js 16.3.4 |
| UI 运行时 | React 19.2.8 / React DOM 19.2.8 |
| 语言 | TypeScript strict mode |
| 三维渲染 | Three.js 0.185.1 + `@react-three/fiber` 9.7.0 + `@react-three/drei` 10.7.8 |
| 状态管理 | Zustand 5.0.15 |
| 图标 | lucide-react 1.41.0 |
| 测试 | Vitest + Testing Library |
| 样式 | 原生 CSS 变量与模块化 class，暂不引入 Tailwind |

---

## 3. VC 界面对齐

本阶段参考材料包括：

- 用户提供的 VC 截图：左侧电子目录、中间 3D 视口、右侧组件属性、底部输出窗口。
- `docs/product_comparison.md`：已有 VC 对标功能说明。
- `else/design/frontend/frontend_design_plan.md`：旧前端设计草案。
- `else/design/frontend/properties_panel_update.ts`：属性面板字段和交互草案。

当前仓库中没有发现完整、可运行的 VC 源码工程，因此本实现不直接复制旧代码，而是迁移其中可复用的信息结构和交互模式。

| VC 功能 | VC 中的典型方式 | 当前项目实现方式 |
|---|---|---|
| 顶部工具栏 | 菜单、工具组、操作按钮集中在顶部 | `HeaderBar` 显示项目名、基础工具按钮、头像和收缩入口。 |
| 电子目录 | 树形目录 + 缩略图列表，可拖拽组件入场 | `AssetLibraryPanel` 分设备模型和场景模型，提供搜索、选中、添加和拖拽数据。 |
| 三维视口 | 网格地面、相机操作、组件选中和可视化 | `SceneViewport` 使用 R3F 渲染 mock 工业设备，占位实现 Orbit、网格、坐标轴和选中高亮。 |
| 组件属性 | 选中对象后编辑名称、坐标、类型、参数 | `PropertiesPanel` 编辑名称、描述、position、rotation，并实时同步到 store 和 Canvas。 |
| 输出窗口 | 显示加载、脚本、运行日志 | `TerminalPanel` 维护本地日志流，记录选择、添加、属性修改和面板操作。 |
| 面板管理 | 面板可固定、收缩、调整尺寸 | `WorkspaceShell` 实现四类面板收缩；`ResizeHandle` 实现左右/底部尺寸调整。 |

---

## 4. 文件结构

```text
frontend/
  app/
    globals.css                  # 全局主题、布局、面板、终端和表单样式
    layout.tsx                   # Next 根布局
    page.tsx                     # 工作区首页入口
  components/
    layout/
      HeaderBar.tsx              # 顶部栏
      ResizeHandle.tsx           # 拖拽调整尺寸手柄
      WorkspaceShell.tsx         # 五区域工作区布局
    panels/
      AssetLibraryPanel.tsx      # 左侧设备/场景资产库
      PropertiesPanel.tsx        # 右侧属性面板
    scene/
      SceneViewport.tsx          # R3F Canvas 容器、灯光、网格、拖拽接收
      SceneObjectMesh.tsx        # 不同设备类型的 mock mesh 渲染与选中高亮
    terminal/
      TerminalPanel.tsx          # 底部输出窗口
  design/
    design.md                    # 本文档，当前前端归档入口
  docs/
    design.md                    # 兼容入口，指向 design/design.md
  lib/
    api-client.ts                # 后端 API 边界封装，目前返回 mock 数据
  mocks/
    catalog.ts                   # 设备模型、场景模型和初始场景对象 mock 数据
  stores/
    useWorkspaceStore.ts         # Zustand 工作区状态
  test/
    workspace-components.test.tsx # 面板组件交互测试
    workspace-store.test.ts      # 状态管理测试
  types/
    scene.ts                     # CatalogAsset / SceneObject / Transform / Log 类型
  package.json
  package-lock.json
  tsconfig.json
  next.config.ts
  vitest.config.ts
```

---

## 5. 核心组件说明

### 5.1 `WorkspaceShell`

负责五区布局与面板状态编排：

- Header 在顶部，可收缩。
- 主体为左侧资产库、中间三维视口、右侧属性面板。
- Footer 为底部终端输出区，可收缩。
- 左右面板和底部面板通过 `ResizeHandle` 调整尺寸。
- 面板收缩后中间三维视口自动占据更多空间。

### 5.2 `HeaderBar`

实现当前项目名称展示、基础工具按钮占位和用户头像占位。工具按钮当前只写入本地日志，不调用后端。

### 5.3 `AssetLibraryPanel`

实现 VC 电子目录的基础形态：

- `设备模型` 与 `场景模型` 两类资源切换。
- 本地搜索过滤，支持名称、描述、tag 匹配。
- 资产选中状态。
- 点击加号或双击资产添加到场景。
- 拖拽时通过 `dataTransfer` 传递 `asset_id`，供三维视口 drop 使用。

### 5.4 `SceneViewport`

三维场景容器，当前只做基础承载：

- 使用 `Canvas` 渲染场景。
- 使用 `OrbitControls` 提供基础视角旋转、缩放和平移。
- 使用 `Grid`、`axesHelper`、灯光和地面构建 VC 风格工作区。
- 支持点击对象选中，空白处取消选中。
- 支持从资产库拖拽模型到视口；当前先按屏幕坐标映射到地面近似位置，后续可替换为精确 raycast 落点。

### 5.5 `SceneObjectMesh`

根据设备类型渲染 mock 占位模型：

| 类型 | 当前表现 |
|---|---|
| `conveyor` | 蓝色传送带，含黑色皮带和黄色/绿色停留点占位标记。 |
| `robot_arm` | 基础机械臂组合几何体。 |
| `workpiece_carrier` | 托盘与 12 个工件阵列。 |
| `storage_rack` | 半透明存储柜和库位面板。 |
| `rotary_table` | 圆柱旋转台占位。 |
| 其他设备 | 通用盒体占位。 |

这些不是最终 GLB/URDF 模型，只用于验证三维承载、选中和属性联动。

### 5.6 `PropertiesPanel`

展示并编辑当前选中对象：

- `设备名称`：可编辑，修改后场景标签同步更新。
- `设备类型`：只读，来自 mock asset type。
- `属性描述`：可编辑，修改后 store 同步。
- `坐标位置 X/Y/Z`：可编辑，修改后 3D 对象位置同步。
- `旋转角度 X/Y/Z`：可编辑，修改后 3D 对象旋转同步。
- `来源 / 实例 ID`：只读，用于调试与后端映射。

### 5.7 `TerminalPanel`

输出本地 mock 日志：

- 初始启动日志。
- 资产选中、添加对象、属性修改、面板收缩等操作日志。
- mock 后端响应追加按钮。
- 清除日志功能。

---

## 6. 状态管理

`useWorkspaceStore` 是当前唯一前端状态入口，维护：

| 字段 | 说明 |
|---|---|
| `projectName` | 当前项目名称。 |
| `panels` | Header / 左侧 / 右侧 / Footer 收缩状态。 |
| `layout` | 左右面板宽度和 Footer 高度。 |
| `assets` | mock 资产列表，后续由 catalog API 替换。 |
| `assetCategory` / `assetQuery` / `selectedAssetId` | 资产库筛选和选中状态。 |
| `sceneObjects` | 当前场景对象实例列表。 |
| `selectedObjectId` | 当前选中三维对象。 |
| `logs` | 终端输出日志。 |

关键 action：

- `togglePanel`：切换面板收缩状态。
- `setLayoutSize`：更新面板尺寸。
- `selectAsset`：选中资产库条目。
- `addAssetToScene`：从资产生成场景实例。
- `selectSceneObject`：选中场景对象。
- `updateSceneObject`：更新名称、描述等基础属性。
- `updateSceneObjectTransform`：更新 position / rotation / scale。
- `appendLog` / `clearLogs`：维护终端日志。

---

## 7. Mock 数据与后端对接点

### 7.1 当前 mock 数据

`mocks/catalog.ts` 包含两类数据：

- `mockCatalogAssets`：设备模型和场景模型资产。
- `mockInitialSceneObjects`：初始托盘分拣场景对象。

当前设备覆盖：机械臂、传送带、工件、物料载具、物料生产台、升降台、存储柜、旋转台，以及两个场景模板。

### 7.2 API 边界

`lib/api-client.ts` 已预留：

```ts
listCatalogAssets(): Promise<CatalogAsset[]>
loadWorkspaceScene(projectId: string): Promise<SceneObject[]>
getApiBaseUrl(): string
```

后续替换 mock 时建议映射到后端：

| 前端需求 | 后端接口方向 |
|---|---|
| 资产库列表 | `GET /api/device-specs`、`GET /api/assets` |
| 项目场景加载 | `GET /api/projects/{project_id}/scene` |
| 添加场景实例 | `POST /api/projects/{project_id}/scene/instances` |
| 修改对象属性/位姿 | `PATCH /api/projects/{project_id}/scene/instances/{instance_id}` |
| 删除对象 | `DELETE /api/projects/{project_id}/scene/instances/{instance_id}` |
| 终端后端日志 | 后续 WebSocket 或 SSE 事件流 |

当前不接 Agent，不调用 `SceneBehaviorGraph` 生成接口。

---

## 8. 三维场景实现方式

三维视口当前使用纯前端 mock 几何体，以便先验证交互闭环：

```text
AssetLibraryPanel
  -> addAssetToScene(asset_id, position)
  -> useWorkspaceStore.sceneObjects
  -> SceneViewport
  -> SceneObjectMesh
  -> PropertiesPanel edits
  -> updateSceneObject / updateSceneObjectTransform
  -> SceneObjectMesh rerender
```

后续接入真实 GLB/URDF 时，建议保留 `SceneObjectMesh` 的设备类型分发入口：

- `asset.apiRef` 读取后端 asset metadata。
- `asset.model_url` 指向 Supabase Storage 或对象存储。
- 传送带仍可保留停留点可视化 overlay，用于显示 stop point occupancy。
- 机械臂后续可按 `DeviceSpec.type_specific_contract.urdf.joints` 映射关节动画。

---

## 9. 验证结果

本轮已完成验证：

| 验证项 | 结果 |
|---|---|
| 依赖安装 | `npm install` 成功。 |
| TypeScript | `npm run typecheck` 通过。 |
| 单元/组件测试 | `npm test` 通过，2 个测试文件，6 个用例。 |
| 生产构建 | `npm run build` 通过。 |
| 本地启动 | `npm run dev -- --hostname 127.0.0.1 --port 3000` 成功，HTTP 200。 |
| 浏览器渲染 | 五个区域均存在，Canvas 正常渲染。 |
| 面板收缩 | 左侧、右侧、底部收缩/展开正常，Canvas 自动扩展。 |
| 资产交互 | 搜索“升降”后筛出升降台；双击添加后对象数量从 7 变为 8。 |
| 属性联动 | 将选中对象名称改为 `Lift Table Browser Verified`，X 坐标改为 `5.25`，右侧面板与场景选中标签同步。 |
| 终端输出 | 选择、添加、属性编辑、面板切换均追加本地日志。 |

浏览器检查中修复过一个真实问题：初始日志时间使用当前时间会造成 Next SSR hydration mismatch。现在初始日志使用固定时间戳，运行中新增日志仍使用真实时间。

当前仍存在来自 Three/R3F 依赖内部的 deprecation warning，例如 `THREE.Clock` 与 `PCFSoftShadowMap`，不影响本阶段功能。

---

## 10. 未完成事项与后续建议

本阶段刻意不实现：

- Agent 聊天、SceneBehaviorGraph 生成、用户打断和重规划。
- 真实后端 CRUD、Supabase Storage 模型加载、Redis/WebSocket 实时状态。
- 复杂仿真控制条、RuntimeSnapshot 播放、信号流可视化。
- GLB/URDF 真模型加载、TransformControls 精确拖拽、框选、多选和 gizmo。
- 移动端适配；当前按桌面端常见分辨率设计。

建议下一阶段顺序：

1. 接入后端 `GET /api/device-specs` 和 `GET /api/projects/{project_id}/scene`，替换 catalog 和 scene mock。
2. 实现实例创建/更新/删除 API client，并用 scene revision 做乐观锁。
3. 引入 GLB loader，先加载 Supabase Storage 中的静态模型。
4. 用 TransformControls 替代属性面板单向输入，形成视口拖动和属性面板双向同步。
5. 接入 WebSocket 日志/运行态事件，但仍先不接 Agent UI。
