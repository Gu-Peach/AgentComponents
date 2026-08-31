# `figmaToM4bComponents` 架构解读

> 从 MCP 挂载 → 特化配置 → 核心工厂 → Mastra Tool 抽象四个视角
> 完整解释 `figmaToM4bComponents` 是如何组织起来的。

---

## 目录

1. [概念澄清: MCP Server vs Tool](#1-概念澄清-mcp-server-vs-tool)
2. [三层源码位置](#2-三层源码位置)
3. [工厂模式主链路](#3-工厂模式主链路)
4. [工厂模式的价值分析](#4-工厂模式的价值分析)
5. [Mastra Tool 抽象是什么](#5-mastra-tool-抽象是什么)
6. [Mastra Tool 在这个项目里的作用](#6-mastra-tool-在这个项目里的作用)
7. [完整全景与一句话总结](#7-完整全景与一句话总结)
8. [Mastra 是 Agent 框架 —— 但只用了一小部分](#8-mastra-是-agent-框架--但这个项目节制地只用了一小部分)
9. [Tool 抽象为什么能被"多协议包装"](#9-tool-抽象为什么能被多协议包装)
10. [跨协议适配成立的前提与边界](#10-跨协议适配成立的前提与边界)
11. [组件推测的真正发生地: getFigmaNodeDataTools](#11-组件推测的真正发生地-getfigmandataoodetools)
12. [为什么规则做完还要 LLM: 识别 vs 合成](#12-为什么规则做完还要-llm-识别-vs-合成)
13. [候选组件识别的算法逻辑](#13-候选组件识别的算法逻辑)
14. [这套方案是人能想出来的吗?](#14-这套方案是人能想出来的吗)
15. [adapter 的传递机制: context propagation](#15-adapter-的传递机制-context-propagation)

---

## 1. 概念澄清: MCP Server vs Tool

**`m4b-d2c` 是 MCP Server (工具包)，`figmaToM4bComponents` 只是其中一个 Tool。**

### 层级对照

| 层级 | 概念 | 例子 |
|---|---|---|
| **协议层** | MCP (Model Context Protocol) | Anthropic 定义的通用协议 |
| **服务层** | MCP Server | `m4b-d2c`（在 `.mcp.json` 里挂的这个）|
| **工具层** | Tool | `figmaToM4bComponents`、`detectFigmaLayoutBlocksTool` 等 |

### `m4b-d2c` MCP Server 挂载的 5 个 Tool

```
m4b-d2c MCP Server (id: 'm4b-d2c', 部署在 4lduzk69.fn.bytedance.net)
  │
  ├─ Tool 1: detectFigmaLayoutBlocksTool   ← 拆布局块 (纯规则)
  ├─ Tool 2: figmaToM4bComponents          ← Figma → m4b yaml (含 LLM)  ★
  ├─ Tool 3: getFigmaImageTool             ← 拿 Figma 图 URL (纯规则)
  ├─ Tool 4: getFigmaMetricsTool           ← 拿 Figma 结构化 metrics (未在 tools/list 暴露)
  └─ Tool 5: getRawFigmaNodeTools          ← 拿 Figma 原始节点 (未在 tools/list 暴露)
```

### 5 个 Tool 的分工

| Tool | 输入 | 输出 | 用途 | 是否有 LLM |
|---|---|---|---|---|
| `detectFigmaLayoutBlocksTool` | figmaUrl + depth/size 参数 | blocks[]（bbox / childBlockIds / layoutMode）| **拆布局** | ❌ 纯规则 |
| `figmaToM4bComponents` | figmaUrl | m4bYamlResult + candidateComponents + required | **主推断: Figma → yaml** | ✅ 多模态 LLM |
| `getFigmaImageTool` | figmaUrl + scale | imageUrl（S3 临时链接）| **拿参考图** | ❌ 纯规则 |
| `getFigmaMetricsTool` | figmaUrl + maxDepth/maxNodes/format | regions[]（结构化 metrics）| **拿视觉度量** | ❌ 纯规则 |
| `getRawFigmaNodeTools` | figmaUrl | 原始 Figma 节点 JSON | **拿原始节点** | ❌ 纯规则 |

**关键观察: 只有 `figmaToM4bComponents` 一个 tool 会调 LLM，其他 4 个都是"数据获取器"。**

### 数据流: 5 个 Tool 如何协作

`figmaToM4bComponents` 内部会主动调用其他几个作为"数据源":

```
figmaToM4bComponents (主 tool)
    │
    │ 内部并行调用 (从 create-figma-to-design-system-tool.ts 源码)
    │
    ├─▶ figmaService.getImageUrlByNode(...)     ← 复用 getFigmaImageTool 的逻辑
    ├─▶ getFigmaMetricsTool.execute(...)         ← 直接内部调用!
    └─▶ getFigmaNodeDataTools.execute(...)      ← 拿原始节点 + 复合结构识别
         (getFigmaNodeDataTools 是 getRawFigmaNodeTools 的加工版)
    │
    │ 3 个 Promise 并发, 全部拿到后
    ▼
组装 Prompt (含图 + metrics 摘要 + 原始节点 + 4 种识别规则)
    │
    ▼
Mastra Agent stream (调多模态 LLM, 输出 yaml)
    │
    ▼
校验 constraints + 注入 rootBounds
    │
    ▼
返回 { m4bYamlResult, candidateComponents, required }
```

### 好处: 为什么这么设计?

1. **用户可以细粒度组合** —— 只想拆块? 直接调 `detectFigmaLayoutBlocksTool`; 想拿图? 调 `getFigmaImageTool`; 走完整流程? 调 `figmaToM4bComponents`
2. **内部复用避免重复实现** —— `figmaToM4bComponents` 不重造轮子, 复用其他 tool
3. **能力解耦、独立演进** —— 未来加新 tool 不影响老 tool

### 类比

**MCP Server ≈ npm package**:

```
npm 包 "lodash"           MCP Server "m4b-d2c"
├── _.map                  ├── figmaToM4bComponents
├── _.filter               ├── detectFigmaLayoutBlocksTool
├── _.debounce             ├── getFigmaImageTool
├── _.chunk                ├── getFigmaMetricsTool
└── ...                    └── getRawFigmaNodeTools

你 require('lodash') 拿到整个包    你在 .mcp.json 挂 "m4b-d2c" 拿到整个 server
用哪个函数是你的事                     用哪个 tool 是模型的事
```

### 回到 `.mcp.json`

```json
{
  "mcpServers": {
    "m4b-d2c": {                                            // ← 一个 MCP server
      "type": "http",
      "url": "https://4lduzk69.fn.bytedance.net/api/mcp/m4b-d2c/mcp",
      "timeout": 120000
    }
  }
}
```

**这一整个引用是"挂载一个 server"，不是"挂载一个 tool"**。挂完之后 Codex 通过 MCP 协议的 `tools/list` 拿到这个 server 里所有可见 tool 的清单。

---

## 2. 三层源码位置

`figmaToM4bComponents` 的源码分成 **3 层**（工厂 → 特化 → 挂载）:

### 第 1 层: **特化配置**（30 行, 最外层）

**路径**: `packages/mastra/src/design-systems/m4b/tools/figma-to-m4b.ts`

```typescript
export const figmaToM4bComponents = createFigmaToDesignSystemTool({
  id: 'figma-to-m4b-components',
  description: '...',
  adapter: m4bDesignSystemAdapter,
  outputField: 'm4bYamlResult',
  enableCachedResult: true,
});
```

只是把工厂参数固定成 "m4b" 版本。真正的实现不在这里。

### 第 2 层: **核心工厂**（632 行, 真正的实现）★

**路径**: `packages/mastra/src/design-systems/tools/create-figma-to-design-system-tool.ts`

**这个才是 `figmaToM4bComponents` 的真正源码**。所有关键逻辑都在这里:

- 缓存查询（`getCachedD2CResult`）
- 3 个 Promise 并发数据获取（image / metrics / rawNodes）
- 4 种复合结构识别 prompt 组装（`buildRepeatedGroupsText` 等）
- Figma metrics 结构化摘要（`summarizeFigmaMetricsForYamlPrompt`）
- LLM stream 调用（`designSystemAgent.stream(...)`）
- 完整性校验（`hasConstraintsSection`）
- YAML 后处理（`injectRootBoundsIntoYaml`、`stripYamlCodeFence`）
- 数据集打点（`datasetService.report`）
- 错误诊断（`formatIncompleteYamlDiagnosticError`）

**关键入口是第 407 行的 `execute` 函数**, 420-630 行是完整链路。

### 第 3 层: **MCP 挂载**（18 行, 注册到 server）

**路径**: `packages/mastra/src/mcp/d2c.ts`

```typescript
export const m4bD2cServer = new MCPServer({
  id: 'm4b-d2c',
  ...
  tools: {
    figmaToM4bComponents,      // ← 挂载到这里
    ...
  },
});
```

MCP 协议把它暴露成一个可调用的 tool。

### 相关依赖文件（第 4 层扩展点）

严格说主链路是上面 3 个, 但真正让 m4b 特化生效的还有 **m4b adapter 触角**:

```
├─ design-systems/m4b/core/adapter.ts               (37 行)
│    ← m4bDesignSystemAdapter 定义, 挂 5 个能力:
│      · componentSignatures        (组件识别规则)
│      · detectComponentCandidates  (候选识别函数)
│      · resolveReferenceDocs       (拿 markdown 说明)
│      · iconMatcher                (m4b 图标匹配)
│      · agent.promptKey='gec.ai.m4b_d2c' (LLM prompt key)
│
├─ design-systems/m4b/detection/
│    ├─ component-signatures.ts     (Table/Popover 等的签名)
│    └─ detect-component-candidates.ts (候选识别)
│
├─ design-systems/m4b/references/*.md               (60+ 组件说明)
│
└─ design-systems/m4b/icons/icon-matcher.ts         (图标)
```

---

## 3. 工厂模式主链路

三层完整职责分工:

```
┌────────────────────────────────────────────────────────────────┐
│  mcp/d2c.ts                (18 行 · MCP 注册层)                 │
│  ────────────────────────                                       │
│  new MCPServer({ id: 'm4b-d2c', tools: { figmaToM4bComponents } })
│                                                                  │
│  职责: 把 tool 塞进 MCP 协议 · 让远端 Codex/Claude 能调          │
└────────────────────────────────────────────────────────────────┘
                             ▲
                             │ 挂载
                             │
┌────────────────────────────────────────────────────────────────┐
│  design-systems/m4b/tools/figma-to-m4b.ts   (30 行 · 特化层)   │
│  ─────────────────────────────────────────                     │
│  export const figmaToM4bComponents =                            │
│    createFigmaToDesignSystemTool({                              │
│      id: 'figma-to-m4b-components',                             │
│      description: '...',                                        │
│      adapter: m4bDesignSystemAdapter,      ← 关键: 传入 m4b 适配器│
│      outputField: 'm4bYamlResult',                              │
│      enableCachedResult: true,                                  │
│    })                                                            │
│                                                                  │
│  职责: 把工厂参数固定成"m4b 版本" · 别的没了                    │
└────────────────────────────────────────────────────────────────┘
                             ▲
                             │ 调用 (工厂函数)
                             │
┌────────────────────────────────────────────────────────────────┐
│  design-systems/tools/create-figma-to-design-system-tool.ts    │
│                              (632 行 · 工厂层 ★ 真正的实现)     │
│  ─────────────────────────────────────                          │
│  export function createFigmaToDesignSystemTool(config) {        │
│    return createTool({                                          │
│      execute: async (input, ctx) => {                           │
│        // 1. parseFigmaUrl                                      │
│        // 2. 查缓存 (spec-server)                                │
│        // 3. 并发拉数据 (image + metrics + rawNodes)             │
│        // 4. 4 种复合结构识别 (repeatedGroups 等)                 │
│        // 5. 组装 prompt (中英夹杂 + 图 + metrics + rules)       │
│        // 6. Mastra Agent stream (多模态 LLM)                    │
│        // 7. 校验 constraints + 注入 rootBounds                  │
│        // 8. dataset 打点                                        │
│        return { m4bYamlResult, candidateComponents, required }  │
│      }                                                          │
│    })                                                            │
│  }                                                              │
│                                                                  │
│  职责: 所有实际推断/调 LLM/后处理 都在这一个 632 行文件里         │
└────────────────────────────────────────────────────────────────┘
```

**关键数字**: 三层合计 **680 行 = 18 (挂载) + 30 (特化) + 632 (工厂)**。

---

## 4. 工厂模式的价值分析

### 工厂模式的 3 个典型特征都在

对照经典工厂模式, 这份代码完全命中:

| 工厂模式特征 | 在这个 D2C 里的体现 |
|---|---|
| **抽象工厂函数** | `createFigmaToDesignSystemTool(config)` |
| **配置参数化** | `id / description / adapter / outputField / enableCachedResult` 五个入参 |
| **产出可复用产品** | 目前产出 2 个: `figmaToM4bComponents` + `figmaToHiuiComponents` |
| **产品接口统一** | 都是 Mastra Tool（`{ id, inputSchema, outputSchema, execute }`）|
| **变化点集中** | 用 `adapter` 承载所有设计系统的差异（组件签名/图标/prompt/references）|
| **共用逻辑** | 缓存/图拉取/LLM 调用/校验/打点 都在工厂里（632 行）|

### 为什么工厂模式在这个场景是必然的

对比两种实现路径:

**不用工厂 —— 每个设计系统重造一份**:

```
figmaToM4bComponents.ts     632 行  ← 100% 复制
figmaToHiuiComponents.ts    632 行  ← 100% 复制, 只有 adapter 不同
figmaToPulseComponents.ts   632 行  ← 未来加新设计系统还得再复制
figmaToArcoComponents.ts    632 行
                          ────────
                          2528 行  · 4 份重复代码
```

改一个 bug 要改 4 个文件——典型的"重复代码地狱"。

**用工厂 —— 目前实际的实现**:

```
factory (工厂)         632 行  ← 共用
m4b/adapter.ts         37 行   ← m4b 特化
m4b/detection/         (若干)  ← m4b 组件识别
m4b/figma-to-m4b.ts    30 行   ← 特化实例
hiui/adapter.ts        37 行   ← hiui 特化
hiui/detection/        (若干)
hiui/figma-to-hiui.ts  30 行
                     ────────
                     ~800 行  · 单份工厂 + 多份薄壳
```

改 bug 只改工厂那 632 行, 所有设计系统同时受益。

### 一份工厂, 两个实例

**`createFigmaToDesignSystemTool` 目前产出 2 个 tool**:

- **m4b 版本**: `figmaToM4bComponents`（消费 `m4bDesignSystemAdapter`）
- **hiui 版本**: `figmaToHiuiComponents`（消费 `hiuiDesignSystemAdapter`）

这就是 `docker/hiui-d2c` 目录存在的原因——**同一套推断骨架适配到多个设计系统**。

---

## 5. Mastra Tool 抽象是什么

### 直接结论

**Mastra Tool = [Mastra 框架](https://mastra.ai) 提供的"AI 工具抽象"**:

- 一个 JS 对象
- 声明**输入/输出的类型**
- 声明**元数据**（id / description）
- 声明**执行函数**（`execute`）
- Mastra 框架能把它**自动适配**到多种协议（MCP / Agent tool call / Workflow node）

**就像 React 的 `Component`、Vue 的 `defineComponent`、Express 的 `Router`——是这个框架的"标准公民"。**

### Mastra 是什么?

**Mastra 是 TypeScript 的 AI Agent 框架**（[mastra.ai](https://mastra.ai)）, 开源, 2024 年发布。定位类似:

- **LangChain（Python）** 的 TS 版本
- 但比 LangChain 更"轻"、类型更好

Mastra 提供的核心抽象有 5 个:

| Mastra 抽象 | 干什么 | 类比 |
|---|---|---|
| `Agent` | LLM 会话主体 | ChatGPT 的一个 assistant |
| `Tool` | 可被 Agent 调用的能力 | function calling 里的 function |
| `Workflow` | 多步骤编排 | LangChain 的 chain |
| `MCPServer` | 打包成 MCP 协议 | 挂载 tools 到 MCP |
| `Memory` | 会话记忆 | vector db / conversation history |

### Mastra Tool 的具体形态

```typescript
import { createTool } from '@mastra/core/tools';
import { z } from 'zod';

const someTool = createTool({
  id: 'figma-to-m4b-components',
  description: '把 Figma 设计稿转成 m4b React yaml',
  
  // ★ 输入 schema (用 zod 类型化)
  inputSchema: z.object({
    figmaUrl: z.string().url(),
  }),
  
  // ★ 输出 schema
  outputSchema: z.object({
    m4bYamlResult: z.string(),
    candidateComponents: z.array(z.string()),
    required: z.string(),
  }),
  
  // ★ 执行函数
  execute: async ({ context }) => {
    const { figmaUrl } = context;
    // ... 做 632 行的事
    return { m4bYamlResult, candidateComponents, required };
  },
});
```

**关键三件套**: `inputSchema` + `outputSchema` + `execute`。这就是 "Mastra Tool" 的最小定义。

### 和你熟悉的东西对比

如果你从其他框架来, Mastra Tool 类似:

| 框架 | 相似抽象 |
|---|---|
| **OpenAI function calling** | `{ name, description, parameters, function }` |
| **LangChain (Python)** | `@tool` decorator |
| **VS Code Extension** | `commands.registerCommand()` |
| **Express** | `router.get('/', handler)` |
| **React** | `Component` |

**共同点**: **一个声明式的"能力单位"，框架负责运行它**。

---

## 6. Mastra Tool 在这个项目里的作用

### 好处 1: **同一个 Tool 定义能被多种消费方式复用**

写一次 Tool, 可以:

```
Mastra Tool (createTool 定义一次)
    │
    ├─▶ 挂到 MCP Server → 变成 MCP tool  (远端 Codex 调用)
    │   new MCPServer({ tools: { figmaToM4bComponents } })
    │
    ├─▶ 挂到 Agent      → 变成 LLM function call
    │   new Agent({ tools: { figmaToM4bComponents } })
    │
    ├─▶ 挂到 Workflow   → 变成 workflow 节点
    │   new Workflow().step(figmaToM4bComponents)
    │
    └─▶ 本地直接调用    → 变成普通 async 函数
        await figmaToM4bComponents.execute({ context })
```

**这就是为什么 [d2c.ts](mastra/mcp/d2c.ts) 只需 18 行**——它只是把已定义好的 Tool 挂到 MCPServer 上:

```typescript
export const m4bD2cServer = new MCPServer({
  id: 'm4b-d2c',
  tools: { figmaToM4bComponents, ... },  // ← 直接挂
});
```

**没有任何"MCP 协议转换代码"**——因为 Mastra 已经把 Tool 抽象和 MCP 协议对齐了。

### 好处 2: **类型安全**（zod + TypeScript）

`inputSchema` 用 zod 定义后:

- **调用方**能自动推断出参数类型
- **运行时**会自动校验参数（不合法直接抛错）
- **文档**（MCP tools/list 返回）自动生成 JSONSchema

```typescript
// TypeScript 自动推断
figmaToM4bComponents.execute({ 
  context: { 
    figmaUrl: "..." // ← 必须是 string.url()
  } 
});

// 传错类型直接编译报错:
figmaToM4bComponents.execute({ 
  context: { figmaUrl: 123 } // ❌ TS error
});
```

### 好处 3: **框架托管的横切能力**

Mastra 自动帮你处理:

- **重试**（tool 失败重试策略）
- **超时**（tool 有 timeout 配置）
- **可观测性**（tool 调用有 trace / logging / metrics）
- **上下文注入**（`ctx.mastra` 拿到 Agent / Memory / Logger）

**这些不用你写**——写普通 async 函数得手工加。

### 为什么这个项目选 Mastra 而不是 LangChain

| 需求 | Mastra 满足吗 |
|---|---|
| TypeScript | ✅ 原生 TS |
| MCP 支持 | ✅ 一等公民 |
| 多模态 LLM | ✅ 用 Vercel AI SDK 底座 |
| Workflow 编排（多 subagent 迭代）| ✅ 有 |
| Agent 支持 promptKey (Fornax)  | ✅ 支持自定义 provider |
| 开源 + 可自托管 | ✅ |

**LangChain 不原生支持 MCP, 得写 adapter 层。Mastra 天生支持 MCP, 这就是选它的关键原因。**

---

## 7. 完整全景与一句话总结

### 完整全景图

```
┌──────────────────────────────────────────────────────────────┐
│  外部 (Codex / Claude Code)                                   │
│    通过 MCP 协议调用 tool                                       │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  MCP Server: 'm4b-d2c'                                        │
│  部署在 4lduzk69.fn.bytedance.net                              │
│                                                                │
│  挂载 5 个 Mastra Tool:                                        │
│    - detectFigmaLayoutBlocksTool                               │
│    - figmaToM4bComponents           ★ 本文主角                 │
│    - getFigmaImageTool                                         │
│    - getFigmaMetricsTool                                       │
│    - getRawFigmaNodeTools                                      │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  figmaToM4bComponents (Mastra Tool)                           │
│  ────────────────────────────────                              │
│  三层实现:                                                       │
│                                                                │
│  [第 3 层] MCP 挂载  · mcp/d2c.ts (18 行)                      │
│         │ new MCPServer({ tools: { figmaToM4bComponents } })   │
│         ▼                                                       │
│  [第 2 层] 特化配置  · m4b/tools/figma-to-m4b.ts (30 行)       │
│         │ createFigmaToDesignSystemTool({                      │
│         │   adapter: m4bDesignSystemAdapter,                   │
│         │   outputField: 'm4bYamlResult',                      │
│         │   enableCachedResult: true                           │
│         │ })                                                    │
│         ▼                                                       │
│  [第 1 层] 核心工厂  · tools/create-figma-to-design-system-... │
│         │           (632 行 ★ 真正实现)                         │
│         │                                                       │
│         │  execute 内部:                                        │
│         │    1. parseFigmaUrl                                   │
│         │    2. 查缓存 (spec-server 0mym4uc8.fn.bytedance.net) │
│         │    3. 并发拉数据 (image + metrics + rawNodes)          │
│         │    4. 4 种复合结构识别                                 │
│         │    5. 组装 prompt (中英夹杂 + 图 + metrics + rules)    │
│         │    6. Mastra Agent stream (多模态 LLM)                │
│         │    7. 校验 constraints + 注入 rootBounds              │
│         │    8. dataset 打点                                    │
│         ▼                                                       │
│  [扩展点] m4b/core/adapter.ts (37 行)                          │
│         · componentSignatures                                   │
│         · detectComponentCandidates                             │
│         · resolveReferenceDocs                                  │
│         · iconMatcher                                           │
│         · agent.promptKey='gec.ai.m4b_d2c'                     │
└──────────────────────────────────────────────────────────────┘
```

### 一句话总结（分层）

- **MCP 层**: `m4b-d2c` 是 MCP Server (工具包), 挂载 5 个 Tool
- **业务层**: `figmaToM4bComponents` 是"重量级"生成型 Tool, 负责 Figma → yaml
- **实现层**: 用工厂模式 (`createFigmaToDesignSystemTool`) + 适配器 (`m4bDesignSystemAdapter`) 组合
- **框架层**: 所有 Tool 都是 Mastra Tool, 用 `createTool()` 定义, 天然支持 MCP 协议
- **多复用**: 同一份 Mastra Tool 定义可以挂到 MCP Server / Agent / Workflow / 本地调用四种消费方式

**最短表达**:

> `figmaToM4bComponents` = 一个 Mastra Tool
> = 用工厂模式 (`createFigmaToDesignSystemTool` 632 行核心) 产出
> = 消费 m4b 适配器 (`m4bDesignSystemAdapter`) 特化
> = 挂到 MCP Server `m4b-d2c` 暴露给远端 Agent
> = 完整链路 = 挂载(18行) + 特化(30行) + 工厂(632行) = 680 行

---

## 附: 推荐阅读顺序

如果你要通读源码, 推荐这个顺序（10 分钟能读通）:

1. **[mastra/mcp/d2c.ts](mastra/mcp/d2c.ts)** (18 行) —— 看 MCP Server 怎么挂载 Tool
2. **[mastra/design-systems/m4b/tools/figma-to-m4b.ts](mastra/design-systems/m4b/tools/figma-to-m4b.ts)** (30 行) —— 看特化配置
3. **[mastra/design-systems/tools/create-figma-to-design-system-tool.ts](mastra/design-systems/tools/create-figma-to-design-system-tool.ts)** (632 行) —— 看真正实现

这份 632 行工厂代码是一份**教科书级别**的 "AI + 工厂模式" 实践, 同时展示了:

1. 纯规则处理（4 种复合结构识别、Figma metrics 摘要压缩）
2. 多模态 LLM prompt 组装（图 + JSON + 中英规则）
3. LLM streaming 调用（Mastra Agent）
4. 完整性校验（`constraints:` 哨兵）
5. 输出后处理（注入 rootBounds、剥离 markdown fence）
6. 缓存 + 打点（20% 采样 dataset）
7. 多设计系统扩展点（adapter 模式）

值得反复精读。

---

## 8. Mastra 是 Agent 框架 —— 但这个项目"节制地"只用了一小部分

### 直接结论

**Mastra 是完整的 AI Agent 框架**——提供 Agent / Tool / Workflow / Memory / RAG 一整套。

**但这个项目只用了它的 2 个能力**:
1. **Tool 抽象**（`createTool` + `MCPServer`）
2. **Agent 调 LLM stream 的能力**（`mastra.getAgentById(...).stream()`）

**其他能力全部没用**（Workflow 编排、Memory 会话记忆、RAG 向量检索、Agent 多轮 tool call 循环）。

### Mastra 完整能力矩阵 vs 本项目使用情况

| Mastra 抽象 | 干什么 | 这个项目用了吗 |
|---|---|---|
| **Tool** | 声明可调用能力 | ✅ 重度使用 |
| **MCPServer** | 打包 Tool 到 MCP 协议 | ✅ 重度使用 |
| **Agent** | LLM 会话主体（含系统 prompt / tool call 循环）| ⚠️ **只用了 `.stream()` 一次调用**, 不用它的多轮循环 |
| **Workflow** | 多步骤编排（决策 / 并行 / 循环）| ❌ 不用 |
| **Memory** | 会话记忆（含向量库）| ❌ 不用 |
| **RAG** | 向量检索 | ❌ 不用 |
| **Evals** | 自动评测 | ❌ 不用（但有 dataset 打点收集数据）|

### 证据: Agent 只用了 `.stream()` 一次调用

看 [create-figma-to-design-system-tool.ts](mastra/design-systems/tools/create-figma-to-design-system-tool.ts) 里实际怎么用 Agent:

```typescript
// 只用一次 stream, 拿到 LLM 输出就完事
const agent = context.mastra.getAgentById(D2C_AGENT_ID);
const yamlResult = await agent.stream(messages, {
  modelSettings: { maxOutputTokens: 24_000 },
});

let result = '';
for await (const chunk of yamlResult.textStream) {
  result += chunk;
}
// result 拿到 yaml, 结束
```

**这是"一次性 LLM 调用"，不是"Agent 循环"**。Agent 的核心价值——**多轮 tool call 循环**（LLM → 决定调 tool → 拿结果 → LLM 继续）——完全没用。

### 类比: **Mastra 是"IKEA 大礼包", 这个项目只拿了 2 块**

```
Mastra 完整包 (IKEA 大礼包):
    ┌────────────────────────────────────────┐
    │ Agent 循环 (多轮 tool call)              │
    │ Workflow 编排 (多步流水线)                │
    │ Memory (会话记忆)                        │
    │ RAG (向量检索)                          │
    │ Evals (自动评测)                        │
    │ ★ Tool 抽象 (createTool)                │  ← 这个项目只用这两块
    │ ★ MCPServer (MCP 打包)                  │
    └────────────────────────────────────────┘

这个项目实际用的部分:
    ┌──────────────────────┐
    │ Tool 抽象             │
    │ MCPServer 打包       │
    │ Agent.stream() (只调 LLM, 不用循环)
    └──────────────────────┘
```

**只用了大礼包里的一小块。**

### 为什么这个项目这么"节制"?

有 3 个技术理由:

#### 理由 1: **MCP 协议是同步 request-response, 不适合 Agent 循环**

MCP 协议的 `tools/call` 是一次调用返回一次结果——**没法承载"Agent 多轮 tool 循环"**。

如果用 Agent 循环:
```
外部 Codex 调 figmaToM4bComponents
    ↓ MCP request
服务端 Agent 开始循环:
    LLM → 想调 tool A (但 tool A 是什么? 外部 Codex 不知道)
    → tool A 结果 → LLM → 想调 tool B → ...
    → 最终 yaml
    ↓ MCP response (要等 5 分钟)
外部 Codex 才拿到结果
```

**MCP 客户端的 timeout 通常是 30-120s**, 撑不住 Agent 循环的长任务。

#### 理由 2: **服务端已经用规则处理了 95% 的工作**

服务端 632 行代码做了大量**规则处理**:

- 4 种复合结构识别（`repeatedGroups` 等）
- Figma metrics 摘要压缩（80 regions 上限）
- 组件签名匹配（`detectFigmaComponentCandidates`）
- 图标匹配（`iconMatcher`）
- 引用文档筛选（`resolveReferenceDocs`）
- LLM 输出后处理（`injectRootBoundsIntoYaml`、`stripYamlCodeFence`）

**规则做了 95%, LLM 只做 5% 的灰色地带决策**——这种场景不需要 Agent 循环。**一次 LLM 调用就够**。

#### 理由 3: **真正需要 Agent 循环的部分在别的地方**

看 [prompts/d2c/d2c-template.md](../ai-stack/prompts/d2c/d2c-template.md) —— **那个才是完整 Agent 循环的地方**:

```
D2C Sandbox Orchestrator (8 轮迭代):
    Iter 0: @d2c-route-builder + @d2c-multimodal-evaluator
    Iter 1-7: @d2c-route-refiner + @d2c-multimodal-evaluator
    Pass: @d2c-iteration-yaml-refiner
```

**这才是真正的 Agent + Workflow 使用场景**——4 个 subagent、8 轮迭代、评测反馈循环。但**这个不走 MCP**, 走 CoCo 云端的 sandbox 长任务。

**架构分工**:

- **MCP 路径 (`figmaToM4bComponents`)** = 快速一次性生成（30-100s, 只调一次 LLM）
- **Sandbox 路径 (D2C Sandbox)** = 慢迭代到达标（8 轮, 多个 subagent）

**两条路径用同一个 Mastra 框架**, 但激活的能力完全不同。这就是**"框架应该像库一样使用"**的实践典范——按需取用，不被框架绑架。

### Mastra 各能力在本项目的使用地图

| Mastra 能力 | 在这个项目里用到吗 | 用在哪 |
|---|---|---|
| **Tool 抽象** | ✅ | `create-figma-to-design-system-tool.ts` 用 `createTool()` |
| **MCPServer** | ✅ | `mcp/d2c.ts` 打包 5 个 tool 到 `m4b-d2c` MCP |
| **Agent（作为 LLM 会话主体）** | ⚠️ 部分 | 只用 `.stream()` 一次性调 LLM, 不用循环 |
| **Agent（多轮 tool call 循环）** | ❌ 主 tool 不用 | 但 CoCo Sandbox 里的 subagent 大概率用 |
| **Workflow** | ❌ 主 tool 不用 | CoCo Sandbox 的 orchestrator 可能用 |
| **Memory** | ❌ | 无会话记忆需求 |
| **RAG** | ❌ | 没做向量检索 |
| **Evals** | ❌ | 但有 dataset 打点（`d2c-figma-data` 20% 采样）|

---

## 9. Tool 抽象为什么能被"多协议包装"

### 核心结论

**Tool 是"能力容器", 协议是"分发通道"。同一份 Tool 定义, 可以被多种协议包装成不同"出口"**。

### 抽象 vs 协议的区别

| 维度 | Mastra Tool | MCP 协议 |
|---|---|---|
| **存在形式** | 内存里的 JS 对象 | 网络上的 JSON 字符串 |
| **依赖** | Node.js 运行时 | HTTP + JSON-RPC |
| **类型系统** | zod / TypeScript | JSONSchema |
| **调用方式** | `await tool.execute({ context })` | `POST /mcp {"method":"tools/call","params":{...}}` |
| **消费者** | 同一进程的代码 | 远端任意语言的客户端 |
| **传输 overhead** | 0（同进程直调）| 有（HTTP + JSON 序列化）|

**Tool 是"给程序员看的"，协议是"给机器传输的"**。抽象可以映射到任何协议, 只要能把两边格式对上。

### 同一个 Mastra Tool, 4 种消费方式

#### 出口 1: **变成 MCP tool**

```typescript
const server = new MCPServer({
  id: 'm4b-d2c',
  tools: { figmaToM4bComponents },
});

// Mastra 内部适配:
// 1. zod schema → JSONSchema (给 MCP tools/list 返回)
// 2. MCP JSON-RPC 协议解析 (tools/call 请求)
// 3. 参数校验 + execute() 调用
// 4. 结果 JSON 序列化返回
```

#### 出口 2: **变成 Vercel AI SDK 的 function calling**

```typescript
import { generateText } from 'ai';

await generateText({
  model: openai('gpt-4'),
  tools: {
    figmaToM4b: figmaToM4bComponents,  // ← 直接挂
  },
  messages: [{ role: 'user', content: '帮我转这个 figma' }],
});

// 底层适配: 转 OpenAI function 格式:
//   {
//     "type": "function",
//     "function": {
//       "name": "figmaToM4b",
//       "description": "...",
//       "parameters": { ...zod 转 JSONSchema... }
//     }
//   }
// LLM 决定调用 → 解析 tool_calls → 触发 execute()
```

#### 出口 3: **挂到 Mastra Agent（Agent 循环）**

```typescript
const agent = new Agent({
  name: 'figma-agent',
  model: openai('gpt-4'),
  tools: { figmaToM4bComponents },
});

await agent.chat('这个 figma 转 yaml');
// Agent 循环: LLM 决定调 tool → 结果塞回 → LLM 继续
```

#### 出口 4: **本地直接调用**

```typescript
const result = await figmaToM4bComponents.execute({ 
  context: { figmaUrl: '...' }
});
// 没协议, 就是普通 async 函数调用
```

### 为什么可以"一对多适配"?

**因为 Mastra Tool 只包含"通用的 3 件事"**:

```
Mastra Tool = {
  元数据:   { id, description }           ← 各协议都需要
  Schema:  { inputSchema, outputSchema }  ← 各协议都能转换
  执行:    { execute }                    ← 各协议都能触发
}
```

**这 3 件事没有任何协议特征**——它是"最大公约数"。任何协议只要能:
1. 表达元数据（name / description）
2. 表达类型信息（转成自己的 schema 格式）
3. 触发执行（把参数塞进 `execute`）

**就能承载这个 tool**。

### 类比: **Java 接口 vs 各种协议实现**

假设有个 Java 接口:

```java
public interface UserService {
    User getUser(String id);
}
```

**这个接口本身就是"内存里的定义"**, 可以被暴露成:

- **REST API**: `GET /users/x` → 内部调 `userService.getUser(id)`
- **gRPC**: `UserService.GetUser(...)` → 内部调同一个方法
- **GraphQL**: `query { user(id: "x") }` → 内部调同一个方法
- **同进程调用**: `userService.getUser("x")` → 直接调

**一个接口，多种"出口"**——每种出口只是"协议适配层", 接口本身不属于任何协议。

**Mastra Tool 的角色一样**：

- **Tool 是"接口定义"**
- **MCP 是"其中一种出口"**（HTTP + JSON-RPC）
- **Vercel AI SDK 是"另一种出口"**（OpenAI function calling 格式）
- **Agent 是"另一种出口"**（内部 tool call 循环）
- **本地调用是"最原生的出口"**

### 物理类比: **国际电源转换器**

```
Mastra Tool 抽象  ≈ 一个国际电源转换器
    │
    │ 一头是通用 USB-C 接口 (你的设备)
    │ 另一头可以插:
    │
    ├─▶ 美标插头 (MCP)              ← Mastra 内置转换
    ├─▶ 欧标插头 (Vercel AI SDK)    ← Mastra 内置转换
    ├─▶ 中标插头 (Agent 内部)        ← Mastra 内置转换
    └─▶ 直接给你 USB (本地调用)     ← 不需要转换

你的设备(Tool)只有一个 USB-C 接口, 不管在哪个国家都能用
```

**Tool 抽象 = 设备本身（跟"哪个国家"无关）**
**MCP / Vercel AI SDK / Agent = 各个国家的插座标准（协议）**

### 抽象层的"防抖"价值

**Tool 抽象比协议更稳定**。

MCP 协议还在快速演进（0.x → 1.0）, 未来可能:
- 加流式响应
- 改鉴权机制
- 加新的 method

**这些变化的成本由 Mastra 承担**——它更新 MCPServer 适配层。**你的 Tool 定义完全不用改**。

这就是**抽象层的"防抖"价值**：**上层协议变化不影响底层实现**。

---

## 10. 跨协议适配成立的前提与边界

### 一个必须澄清的怀疑

**光"包装"不够——如果各协议的底层处理逻辑完全不同, 光包装是没用的**。

那 Mastra Tool 抽象为什么能生效?

### 答案: **所有主流 AI Tool 协议已经收敛到同一套心智模型**

看这张对比表——**不同协议在语义层惊人一致**:

| 语义要素 | OpenAI function calling | Anthropic tool use | MCP | Mastra Tool |
|---|---|---|---|---|
| 工具**名字** | `function.name` | `name` | `name` | `id` |
| 工具**说明** | `function.description` | `description` | `description` | `description` |
| 输入**参数** schema | `parameters` (JSONSchema) | `input_schema` (JSONSchema) | `inputSchema` (JSONSchema) | `inputSchema` (zod) |
| 输出格式 | 弱约束（LLM 输出的 JSON string） | 弱约束 | 弱约束（result） | `outputSchema` (zod) |
| 触发**方式** | LLM tool_calls | LLM tool_use block | JSON-RPC method 调用 | `execute()` 函数 |
| 参数**传入** | JSON 对象 | JSON 对象 | JSON 对象 | context 对象 |

**几乎一模一样**——只是字段名叫法不同、传输容器不同、类型系统不同。**核心心智模型完全一致**。

### 为什么会这么统一?

**因为它们本质都在做同一件事**:

```
"给 LLM 一个可调用的能力"

需要什么信息? 
    ├─ 这个能力叫什么 (name)
    ├─ 干什么用 (description) 
    ├─ 传什么参数 (input schema)
    └─ 出什么结果 (output)

需要什么触发? 
    └─ 一次输入 → 一次输出的 request/response 模式
```

**这就是"函数调用"的抽象**——所有编程语言里都存在的通用概念。AI Tool 协议只是**给 LLM 也表达这个抽象的一种方式**。

### 历史演进: 行业标准的收敛路径

```
2022  OpenAI function calling 出现 (定义了 name/description/parameters)
   ↓ 大家学 OpenAI 的做法
2023  Anthropic tool use (基本沿用) 
   ↓ 试图统一
2024  MCP 协议 (显式沿用)
   ↓ 现在
2025  所有协议在语义层已经趋同
```

**这就是"事实标准"的力量**。Mastra Tool 能做通用抽象, **因为 AI Tool 领域已经默认收敛了心智模型**。

**反例**: 如果各协议还在"混战期"（比如 2022 年 6 月）, 那时候写"通用抽象"会很难——因为标准还没定。**现在能这么写, 是搭了行业收敛的便车**。

### 但通用抽象也有边界

**并非所有协议特性都能用这套抽象覆盖**——有些能力会在跨协议时退化:

#### 边界 1: **流式响应**

- MCP 1.0 → 支持 streaming（`notifications/progress`）
- OpenAI function calling → 不支持流式（tool_call 是原子的）

**处理方式**: Mastra 让 `execute` 里可以调 `writer.write()` 手工推流。但**这个能力在 OpenAI 协议里没意义**（会被忽略）。

#### 边界 2: **多轮子调用**（一个 tool 内部再调其他 tool）

- Agent 框架里 tool 可以再触发 tool（"agentic tool"）
- MCP 里 tool 是"叶子节点", 不能再调 tool

**处理方式**: Mastra 让 `execute` 内部拿到 `mastra` 对象, 可以直接调其他 tool（在 Agent 场景生效）。但**这种能力挂到 MCP 时会被扁平化**。

#### 边界 3: **权限/审计元数据**

- 内部 Agent 需要"这个 tool 只有 admin 能用"
- MCP 协议本身没定义权限层

**处理方式**: Mastra 支持在 tool 上加 `permissions` 元字段, 但**转 MCP 协议时可能丢失**。

#### 边界 4: **特殊参数类型**（文件流、二进制）

- OpenAI function calling 参数**只能是 JSON**（不支持 binary）
- MCP 支持 embedded resources（可以传图/文件）

**处理方式**: 如果 tool 参数需要 binary, **MCP 版本能用, OpenAI 版本用不了**——同一个 tool 无法完全跨协议。

### 精确表述

**"Mastra Tool 覆盖了大多数 agent 工具接口"** 的精确版本:

> **Mastra Tool 抽象覆盖了所有主流 AI Tool 协议的"通用子集"**——命名、说明、类型化输入输出、请求-响应式执行。这个子集能满足 **90%+ 的 tool 场景**。少数需要协议特殊能力（流式、多轮、权限、binary）的 tool, 可能在某些协议出口下能力会退化。

### 一个更深层的观察

**Mastra Tool 抽象的存在本身, 就是 AI Tool 生态成熟的证据**。

早期（2022 之前）, "AI 应用"每家自己一套接口, 做通用抽象几乎不可能。现在（2025）, 行业心智模型统一了, 这类"胶水层框架"（Mastra / LangChain / LlamaIndex）才能繁荣。

**从这个角度看, Mastra Tool 抽象的存在, 反映了 AI Tool 生态已经过了"混战期"进入"标准收敛期"**——类似 2000 年前后的 Web 协议（HTTP + JSON 逐渐成为事实标准）。

### 最终三层总结

沿着"Tool 抽象为什么能跨协议"这条思路, 完整答案分三层:

**第 1 层 · 什么是 Tool 抽象**:
> Tool 只是包含 `id / description / inputSchema / outputSchema / execute` 5 件事的 JS 对象。

**第 2 层 · 为什么它能跨协议**:
> 因为它抽取了所有主流 AI Tool 协议的"最大公约数", 各协议只需要写"格式适配层"就能承载它。

**第 3 层 · 为什么这种抽象能成立**:
> 因为 AI Tool 领域已经收敛到同一套心智模型（OpenAI function calling → Anthropic tool use → MCP 都沿用）, 通用抽象搭了"行业收敛"的便车。

**边界**:
> 少数协议特殊能力（流式、多轮子调、权限、binary）在跨协议时会退化, 主流 90%+ 场景 Mastra Tool 都覆盖得住。

**这三层的顺序**: **具体 → 通用 → 元层**——从"这是什么"到"为什么这样设计"再到"这种设计能成立的前提"。理解到第三层, 才算真正吃透一个技术抽象。

---

## 11. 组件推测的真正发生地: `getFigmaNodeDataTools`

### 一个必须澄清的误解

之前反推 `figmaToM4bComponents` 时说 "**LLM 是多模态模型, 通过看 Figma 图 + JSON 推断组件**" —— **这个说法是错的**。

**真相**:

- **组件识别** = **纯规则 + 打分**（在 `getFigmaNodeDataTools` 里）
- **LLM 的工作** = **拿已识别好的 candidates + 复合结构结果, 生成 yaml JSX 树** (在 `figmaToM4bComponents` 里)

**LLM 不做组件"识别", 只做"根据识别结果生成结构化输出"**。

### 铁证: `getFigmaNodeDataTools` 无 LLM 调用

`packages/mastra/src/tools/get-figma-node.ts` 是一个 **2765 行的巨型 tool**。跑 grep 验证:

```bash
grep -c "stream\|getAgentById\|mastra\." get-figma-node.ts
# stream        → 0 命中
# getAgentById  → 0 命中
# mastra.       → 0 命中 (没访问 mastra context)
```

**2765 行代码 = 0 个 LLM 调用**。100% 是规则算法 + Figma REST 调用。

### `getFigmaNodeDataTools` 内部完整链路 (9 步)

```
getFigmaNodeDataTools.execute(input)
    │
    ▼
Step 1: parseFigmaUrl(input.figmaUrl)  → { fileKey, nodeId }
    │
    ▼
Step 2: figmaService.getRawNode(fileKey, nodeId, privateToken)
    → 调 Figma REST API 拉原始节点树
    → rawApiResponse (巨大 JSON)
    │
    ▼
Step 3: simplifyRawFigmaObject(...)
    → 遍历原始树, 剪枝 + 简化
    → 判断"能否折叠成 IMAGE-SVG": 
        FRAME/GROUP/INSTANCE 没有组件身份 + canCollapseContainerToSvg
        → 折叠成 IMAGE-SVG, 丢子节点
    → simplifiedDesign (剪枝后的简化树)
    │
    ▼
Step 4: designSystemAdapter.detectComponentCandidates(simplifiedDesign)   ★ 组件识别在这里
    → 从 m4b/hiui adapter 的 componentSignatures 匹配规则
    → 输出:
      · candidateComponents: ['Table', 'Popover', ...]
      · candidateNodes: [{ nodePath, candidates: [{component, score, reasons}] }]
      · candidateDebugNodes: (阈值前的原始)
    │
    ▼
Step 5: designSystemAdapter.iconMatcher.annotateResolvedIconsInPayload(...)
    → 图标匹配 (regex/关键词 + m4b 图标 manifest)
    │
    ▼
Step 6: annotateVisualAssetsInSinglePass(...)
    → 一次遍历打各种视觉标 (asset 类型/资源 URL 占位)
    │
    ▼
Step 7: Promise.all([
    attachResolvedSvgAssets(...),        ← 拉 SVG 资源 (Figma image API)
    attachResolvedImageAssets(...)       ← 拉图片
])
    │
    ▼
Step 8: 复合结构识别 (4 种)
    · detectRepeatedGroups          → repeatedGroups[]
    · detectDiscreteStatusBlocks    → discreteStatusBlockGroups[]
    · detectMetricCardGroupHeaders  → metricCardGroupHeaders[]
    · normalizeTableRowClips        → tableRowClipSummaries[]
    │
    ▼
Step 9: 序列化 + 返回
    → figmaNodeData: YAML string (整棵剪枝后的树, 给 LLM 看)
    → rootBounds
    → 各种识别结果 (candidateComponents/candidateNodes/matchedIcons/repeatedGroups/...)
```

**依赖只有 2 个**: `figmaService` (Figma REST 客户端) + `designSystemAdapter` (规则匹配)。

### 组件推测的机制: "签名 + 打分"

组件识别在 `designSystemAdapter.detectComponentCandidates()` 里, 由**两个规则库**支撑:

| 文件 | 行数 | 内容 |
|---|---|---|
| `design-systems/m4b/detection/component-signatures.ts` | **3364 行** | 每个 m4b 组件的签名规则 (Table/Popover/... 长什么样) |
| `design-systems/m4b/detection/detect-component-candidates.ts` | **1406 行** | 匹配算法 (遍历节点 × 逐 signature 打分) |

**签名 + 打分 模型 (概念代码)**:

```typescript
const TableSignature = {
  component: 'Table',
  matchers: [
    { predicate: hasChildOfType('ROW'),       score: 30, reason: 'has ROW children' },
    { predicate: hasHeaderRow(),              score: 20, reason: 'has header row' },
    { predicate: nodeNameContains('table'),   score: 15, reason: 'name contains "table"' },
    { predicate: hasAlignedGrid(),            score: 25, reason: 'aligned grid layout' },
    { predicate: hasPaginationSibling(),      score: 10, reason: 'has pagination sibling' },
  ],
  threshold: 50,
};

// 遍历所有节点 × 所有签名
for (const node of nodes) {
  for (const signature of allSignatures) {
    let score = 0;
    const reasons = [];
    for (const matcher of signature.matchers) {
      if (matcher.predicate(node)) {
        score += matcher.score;
        reasons.push(matcher.reason);
      }
    }
    if (score >= signature.threshold) {
      candidates.push({ node, component: signature.component, score, reasons });
    }
  }
}
```

**每个组件识别 = 一份签名 + 一个阈值**。**规则透明可追溯**（每个匹配都带 `reasons` 数组）。

### 完整分工图 (修正之前所有反推)

```
figmaToM4bComponents (632 行工厂)
   │
   │ Step 3: 并发拉 3 份数据
   │
   ├──▶ figmaService.getImageUrlByNode      ← 纯规则 (Figma image API)
   │
   ├──▶ getFigmaMetricsTool.execute         ← 纯规则 (Figma REST + 度量提取)
   │
   └──▶ getFigmaNodeDataTools.execute       ← 纯规则! 2765 行, 0 LLM
        │
        │  内部依赖:
        │  ├─ figmaService (Figma REST)
        │  └─ designSystemAdapter (m4b/hiui)
        │       │
        │       └─▶ detectComponentCandidates
        │              │
        │              └─▶ component-signatures.ts (3364 行规则库)
        │              └─▶ detect-component-candidates.ts (1406 行匹配算法)
        │
        │ 返回:
        │   figmaNodeData (YAML 剪枝树)
        │   candidateComponents ★ ← 组件推测结果
        │   candidateNodes ★     ← 每节点带 reasons 的详细归因
        │   matchedIcons
        │   repeatedGroups / discreteStatusBlockGroups
        │   metricCardGroupHeaders / tableRowClipSummaries
   │
   ▼
figmaToM4bComponents 拿到 3 份数据后
   ▼
组装 prompt (含 Figma 图 + metrics + node data + 4 种识别 + candidates)
   ▼
调 LLM (agent.stream)     ★ 全链路唯一的 LLM 调用点!
   ▼
输出 m4bYamlResult
```

### 关键洞察: LLM 只在最后一步

**整个 D2C 链路里, LLM 只被调用 1 次** —— 在 `figmaToM4bComponents` 的 Step 5 组装完 prompt 之后:

| Tool | 是否有 LLM |
|---|---|
| `figmaService.getRawNode` | ❌ Figma REST |
| `figmaService.getImageUrlByNode` | ❌ Figma image API |
| `getFigmaImageTool` | ❌ 纯代理 figmaService |
| `getFigmaMetricsTool` | ❌ 纯规则度量提取 |
| `getFigmaNodeDataTools` | ❌ **规则算法 + 组件识别 (2765 行)** |
| `detectFigmaLayoutBlocksTool` | ❌ 纯规则拆块 |
| `figmaToM4bComponents` | ✅ **唯一的 LLM 调用点** |

### 更精确的"规则 vs LLM"比例

**修正之前的"5% LLM, 95% 规则"估算**——按代码量算实际是:

```
figmaToM4bComponents (工厂)         632 行  (其中 5% LLM 调用 + 95% 规则)
getFigmaNodeDataTools              2765 行  (100% 规则)
component-signatures (m4b 签名库)   3364 行  (100% 规则)
detect-component-candidates        1406 行  (100% 规则)
其他 tool (image/metrics/detect)   ~500 行  (100% 规则)
────────────────────────────────────────
                                  ~8700 行代码里, LLM 调用只在 5-10 行
                                  → 规则占 99.9%!
```

**LLM 只是"最后一里路的润色"**——90%+ 工作已经被规则做完了。

### 为什么这样设计? 3 个好处

#### 好处 1: **可解释性**
每个 candidate 带 `reasons` 数组, 能明确说 "这个节点是 Table 因为 (a) 有 ROW 子节点 (b) 名字含 table (c) 对齐网格"。**LLM 判断做不到这种可追溯**。

#### 好处 2: **成本可控**
2765 行规则运行只需毫秒级 CPU 时间。如果用 LLM 识别每个 node, 会是**百倍成本 + 百倍延迟**。

#### 好处 3: **可回归测试**
规则代码可以单元测试, 保证"这个 Figma 稿永远识别成 Table"。**LLM 判断不稳定**, 同一输入两次可能得不同结果。

### 修正后的架构定位

| 组件 | 职责 | 技术 |
|---|---|---|
| `getFigmaNodeDataTools` (2765 行) | **组件识别 + 复合结构识别** | 纯规则 |
| `component-signatures.ts` (3364 行) | **每个组件的签名规则库** | 纯规则 |
| `detect-component-candidates.ts` (1406 行) | **签名匹配算法 + 打分** | 纯规则 |
| `figmaToM4bComponents` (632 行) | **拿识别结果组装 prompt + 调 LLM 生成 yaml** | 规则 95% + LLM 5% |
| **LLM (Agent stream)** | **拿 candidates + 结构信息, 生成 JSX yaml 树** | 唯一 LLM 环节 |

### 一句话总结

> **`getFigmaNodeDataTools` 是纯规则 tool (2765 行, 无 LLM/subagent), 依赖 `component-signatures.ts` (3364 行规则库) + `detect-component-candidates.ts` (1406 行匹配算法) 做组件识别**。**LLM 只在最外层 `figmaToM4bComponents` 生成 yaml 时调用 1 次**——它拿到的是已经被规则识别好的 candidates + 复合结构, 只需把这些"翻译"成 JSX yaml 树。**整个 D2C 系统里, 代码量层面规则占 99.9%, LLM 只占 0.1%, 但 LLM 那 5-10 行调用占据 90% 的耗时**。

### 反思: 为什么之前的反推错了

之前我们以为 LLM 是多模态视觉判断——**因为 prompt 里确实塞了 Figma 图片**。但**LLM 拿图不是为了识别组件**, 而是**用来恢复"布局骨架/分组关系/叠层关系"** (prompt 里就这么写的)。**组件的具体类型判断已经在规则层完成了**。

**这纠正了一个常见误解**: "AI 应用 = LLM 判断 + 规则辅助"。**实际生产系统往往反过来**: **规则判断 + LLM 辅助生成**。规则做能确定的事, LLM 做需要"合成/表达"的事——**LLM 是"翻译员", 不是"判断员"**。

---

## 12. 为什么规则做完还要 LLM: 识别 vs 合成

### 一个必须澄清的疑问

**"`getFigmaNodeDataTools` 已经识别出候选组件了, 为什么还要 LLM?"**

**答案**: 因为**规则做完了"识别 (Recognition)", 但没做"合成 (Synthesis)"**。

**两件事本质不同**:
- **识别** = 从有限集合里挑标签 (Table? Popover? Flex?)
- **合成** = 从无限空间里造代码 (columns 怎么写? data 怎么绑? 灰色地带如何决策?)

### 规则给完 candidates 还不能直接跑代码

即使规则告诉你"这里是 Table, 这里是 Popover", 5 个问题规则解决不了:

#### 问题 1: **组件的 props 该怎么填?**

规则知道"这是 Table" —— **但**:
- `columns` 数组怎么定义? 从哪些 Figma 节点抠出来?
- `data` 怎么绑? 用 `logic.data` 还是硬编码?
- `pagination` 怎么配? `sortable` 是否启用?
- 每列的 `title` / `dataIndex` / `render` 怎么写?

**规则给不出**——因为**"识别是 Table"和"生成能跑的 Table"之间隔着大量业务判断**。

#### 问题 2: **多个候选如何选择?**

同一个节点同时匹配多个组件:
```
'root>filter-bar' 候选:
  - Filter (score: 0.90)
  - Filters (score: 0.92)
  - Toolbar (score: 0.88)
```

**规则打了分, 但最后选哪一个?** 需要"综合上下文的判断"——规则不敢定死, 由 LLM 决策。

#### 问题 3: **纯 FRAME 该识别成什么? (灰色地带)**

- `FRAME + auto-layout` → 明确是 `Flex`
- `INSTANCE` → 明确是 `<组件名>`
- **`纯 FRAME (无 auto-layout)`** → **规则给不出定论**
  - 有 backgroundColor + borderRadius → 可能是 Container (独立单元)
  - 无背景, 只是分组 → 可能是 Flex (纯布局)
  - 有阴影 → 可能是 Card

**这些"半结构化半语义化"的节点必须靠 LLM 综合视觉判断**。

#### 问题 4: **文本节点里的内容怎么放?**

规则知道有 "$27,183.00" 这个文本, **但不知道**:
- 是数据字段 `{price}` 还是硬编码?
- "Current price" 是静态 label 还是 i18n key?

**需要语义理解, 规则做不到**。

#### 问题 5: **如何组合成 JSX 树?**

即使每个节点都识别出组件了, 最后还得**组合成一份合法的 React JSX 结构** —— **这是一份完整的"代码合成任务"**, 规则给的是原料, **装配成能跑的 JSX 树需要"生成能力"**。

### 分工的本质区别

```
┌─────────────────────────────────────────┐
│ 规则层 (getFigmaNodeDataTools)           │
│ ─────────────────────                    │
│ 输入: Figma 原始 JSON                     │
│ 输出:                                     │
│   · 剪枝后的节点树                          │
│   · candidateComponents (候选)             │
│   · candidateNodes (打分 + 理由)          │
│   · 重复/表格/图标结构识别                  │
│                                          │
│ 做的事: 识别 (Recognition)                │
│ 特点: 可枚举, 有清晰规则                    │
│ 强项: 快 · 稳定 · 可解释                    │
│ 弱项: 无法生成新的组合                      │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│ LLM 层 (figmaToM4bComponents 里的 stream) │
│ ─────────────────────                    │
│ 输入: 规则层的所有产物 + Figma 图 + prompt │
│ 输出:                                     │
│   · 完整的 JSX yaml 树                     │
│   · props 具体值                          │
│   · imports 语句                          │
│   · meta.description                     │
│   · constraints 段                        │
│                                          │
│ 做的事: 合成 (Synthesis)                  │
│ 特点: 需要综合判断, 组合无穷              │
│ 强项: 灵活生成, 处理灰色地带                │
│ 弱项: 慢 · 不稳定 · 有幻觉                  │
└─────────────────────────────────────────┘
```

### 类比: 搭乐高

**规则层 = 分拣积木**:
- 把散件按类型分堆 (candidateComponents)
- 每个散件贴标签 "这是轮子/门/窗户" (candidateNodes)
- 找出成组的 (repeatedGroups)

**LLM 层 = 拼装成模型**:
- 决定拼什么: 汽车/卡车/挖掘机
- 决定用哪些零件: 4 个轮子里选哪 4 个装哪里
- 决定拼装顺序: 底盘先还是车身先
- 最终产出: 一份"拼装说明书" (yaml)

**规则给的是"零件清单", LLM 给的是"最终作品的说明书"**——**"清单"不能直接玩, 得先拼起来**。

### 澄清"多轮 agent" 的两条路径

**MCP 路径 (`figmaToM4bComponents`)**: **只调 LLM 1 次**, 不是多轮 agent

```typescript
const yamlResult = await agent.stream(messages, {
  modelSettings: { maxOutputTokens: 24_000 },
});
// 一次调用, 拿到 yaml, 结束
```

**Sandbox 路径 (CoCo 云端)**: **多轮 subagent 循环**

```
D2C Sandbox Orchestrator (8 轮迭代):
    Iter 0: @d2c-route-builder + @d2c-multimodal-evaluator
    Iter 1-7: @d2c-route-refiner + @d2c-multimodal-evaluator
    Pass: @d2c-iteration-yaml-refiner
```

**两条路径的对比**:

| 维度 | MCP 路径 | Sandbox 路径 |
|---|---|---|
| LLM 调用次数 | 1 | N × 2 (最多 16) |
| 输出形态 | yaml (原料) | React 项目代码 |
| 是否有反馈循环 | ❌ | ✅ 多模态 evaluator 打分 |
| 是否用 Agent 循环 | ❌ 只用 `.stream()` | ✅ 完整 subagent orchestration |
| 部署形态 | 无状态 FaaS | 有状态 sandbox |
| 耗时 | 30~100s | 5~15 分钟 |

**为什么 Sandbox 需要多轮?** —— 因为**一次生成的代码达不到目标 fidelity**, 需要"生成-评测-修正"闭环反复迭代。**这是 AI 系统"自我修正"能力**——**单次生成永远不完美, 但多轮迭代能收敛到高质量**。

**为什么不把多轮迭代放进 MCP?** —— MCP 协议 timeout 30-120s, 撑不住 5-15 分钟长任务。

### 一句话总结

> **规则做完 candidates 只是"给 LLM 提供好用的原料", 不是"代替 LLM 完成任务"**。LLM 要做的是**"合成完整代码 yaml"**——这需要综合判断、组合决策、灰色地带兜底, 是**无限生成空间**, 规则搞不定。**MCP 路径只调 1 次 LLM (合成一次性 yaml), Sandbox 路径调多次 LLM (迭代修正到 fidelity 达标)**——两条路径分工不同, 都需要 LLM + 规则。

---

## 13. 候选组件识别的算法逻辑

### 输入不是 yaml, 是 JS 对象 (澄清)

**规则处理阶段全程用 JS 对象** (`FigmaLikePayload`), 递归访问属性 (`node.name`, `node.children`, `node.layout.mode`), 不涉及 yaml 序列化/反序列化——性能更好。

**yaml 化只发生在"喂给 LLM 之前"**——因为 LLM 处理 yaml 比 JSON 更省 token。

### 三个阶段, 六个核心函数

```
阶段 A: 打分 (Scoring)
├─ 1. detectFigmaComponentCandidates  ← 入口, 遍历所有 root
├─ 2. walkNode                        ← 递归遍历树
├─ 3. scoreNodeCandidates             ← 对一个节点跑所有签名
└─ 4. scoreSingleSignature            ← 对一个 (节点, 签名) 打分

阶段 B: 过滤 (Filtering)
└─ 5. suppressContainedCandidates     ← 同节点内抑制

阶段 C: 后处理 (Post-processing)
└─ 6. applyContainmentRules           ← 跨节点祖先-后代抑制
```

### 核心打分逻辑: `scoreSingleSignature`

**第一部分: 6 维通用累加**

```typescript
// 维度 1: 节点名匹配                   +0.30
// 维度 2: Figma component 名匹配         +0.35
// 维度 3: 子节点名匹配                    +0.10
// 维度 4: 布局模式匹配                    +0.05
// 维度 5: 预定义结构匹配器                +0.25
// 维度 6: 结构规则匹配                    +0.20
// 满分上限 = 1.25
```

**关键设计**:
- **没有单一维度就够**——最强的 componentName 才 0.35
- **至少 2-3 个维度组合命中**才能过 0.9 强候选阈值
- **每个 reason 都记录**——完全可追溯

**第二部分: 20+ 条硬编码"强信号覆写"**

```typescript
if (signature.name === 'Table' && structureMatcherMap.headerRowWithMultipleBodyRows(node)) {
  score = Math.max(score, 0.92);   // ← 直接拉到 0.92, 跳过累加
}

if (signature.name === 'Modal' && isSelfNamedModalOrDrawerSignal(node, payload, 'modal')) {
  score = Math.max(score, 0.96);   // ← Modal 最高 0.96
}

// ... AI Button / AI Container / AI DatePicker / TagInput / TimePicker / Select / 
//     Input / TextArea / InputTag / Upload / InputNumber / Dropdown ...
// 共 20+ 条强信号
```

**为什么"强信号覆写"?**
- **弱信号**处理"看起来像"的模糊情况
- **强信号**处理"明确是"的确定情况 (设计师明确命名 / 明确结构)
- **兼顾覆盖率和准确率**

### 两级阈值分流

```typescript
const STRONG_CANDIDATE_THRESHOLD = 0.9;  // 正式候选
const DEBUG_CANDIDATE_THRESHOLD = 0.7;   // 记录接近命中的
```

**0.7 debug 阈值的价值**:
- 排查为什么某个组件没被识别 (可能只差 0.05)
- 迭代签名规则 (加分维度让它过 0.9)
- 调试模型输出偏差

### 两级抑制机制

#### 抑制 1: **同节点内抑制** (`suppressContainedCandidates`)

**问题**: 一个节点同时命中 Table (0.92) + Container (0.91) + Flex (0.90)。

**解决**: 按分数从高到低排序, 高分组件的 `containsTargets` 抑制其他候选:
```
Table.containsTargets = ['Container', 'Flex']
→ 抑制 Container 和 Flex, 只保留 Table
```

#### 抑制 2: **跨节点祖先-后代抑制** (`applyContainmentRules`)

**问题**: 父节点识别为 Table, 子节点里的每一行又识别为 Row/Cell。

**解决**: 按节点深度排序 (浅→深), 处理时查已识别的祖先, 用祖先的 `containsTargets` 抑制后代:
```
父节点是 Table (containsTargets = ['Row', 'Cell'])
  └── 子节点候选 Row → 被抑制
  └── 子节点候选 Cell → 被抑制
```

**注意深度排序的必要性**: 不排序抑制会失效——先处理子节点时, 祖先还没记录, 抑制不到。

### 组件列表的固定前缀

```typescript
const components = [
  'Flex', 'Container',                          // ← 保底组件永远前置
  ...componentSet.filter(c => c !== 'Flex' && c !== 'Container')
];
```

**Flex/Container 永远在最前**——这是"保底组件", LLM 生成时至少能用它们兜底。

### 完整走一遍 (SKU 卡片列表页)

```
输入 Figma 节点树:
  root: FRAME (SKU List Page)
    ├── FRAME (Filters bar)
    │     ├── INSTANCE (Filter 1)
    │     └── INSTANCE (Filter 2)
    └── FRAME (SKU List)
          ├── FRAME (SKU Card 1)
          └── FRAME (SKU Card 2)

阶段 A: 递归打分
  root:        [Container (0.95)] ← AI 容器强信号
  Filters bar: [Filters (0.92)]
  Filter 1/2:  [Filter (0.90)] ← 累加过阈值
  SKU List:    [Flex (0.90)]
  SKU Card 1/2: [Container (0.92)]

阶段 B: 同节点抑制 (本例每个节点只命中 1 个组件, 无作用)

阶段 C: 跨节点抑制
  root → Filters bar/SKU List: Container 不抑制 Filters/Flex
  Filters bar → Filter 1/2: Filters.containsTargets = ['Filter'] 
                            → Filter 1/2 被抑制 (跳过)
  SKU List → SKU Card 1/2: Flex 不抑制 Container

最终输出:
  components: ['Flex', 'Container', 'Filters']
  nodes: [root, Filters bar, SKU List, SKU Card 1, SKU Card 2] (5 个带 reasons)
```

### `containsTargets` 是关键的领域知识

```typescript
{ name: 'Table', containsTargets: ['Container', 'Flex', 'Row', 'Cell'] }
{ name: 'Filters', containsTargets: ['Filter'] }
```

**这不是通用规则, 是"领域专家知识"**——需要熟悉 m4b 组件库的工程师梳理"哪些组件在语义上包含哪些子组件"。**规则库最有价值的部分**。

### 一句话总结

> **`detect-component-candidates.ts` = "树遍历 (DFS) + 多维打分 (6 维累加 + 20+ 强信号覆写) + 两级阈值 (0.9/0.7) + 两级抑制 (同节点/跨节点)"**。每个 candidate 都带 `reasons` 数组, 可解释、可迭代、可回归测试, 可通过换 adapter 支持多设计系统 (m4b/hiui)。

---

## 14. 这套方案是人能想出来的吗?

### 直接结论

**能, 但不是"设计"出来的, 是"踩坑积累"出来的**。

代码里到处都是"生产工程的疤痕", **反而是它不那么完美才最像人写的**。

### 6 条证据: 这是"演化涌现"不是"设计先行"

#### 证据 1: **20+ 条硬编码强信号的分数五花八门**

分数 0.92 / 0.94 / 0.95 / 0.96 不统一, 明显是不同时期/不同人/不同 bug 补丁的堆叠:

```typescript
Math.max(score, 0.92);  // Table headerRow
Math.max(score, 0.94);  // AI DatePicker
Math.max(score, 0.95);  // TagInput
Math.max(score, 0.96);  // Modal 自命名
```

**真正设计出来的方案会用统一枚举** (`SIGNAL_CONFIDENCE.strong = 0.9`), 不会这么零碎。**每条规则都被独立调过、独立测过**——是"事故驱动"的产物。

#### 证据 2: **两级阈值 (0.9 / 0.7) 是被迫的**

**为什么是 0.9 和 0.7? 不是 0.85 和 0.65?** —— 大概率是:
1. 开始只有 0.9
2. 发现有些 Table 没被识别 (差 0.05)
3. 加 debug 阈值 0.7 记录"接近命中"的
4. 分析 debug 数据, 迭代签名规则

**典型的"生产事故驱动调优"路径**, 不是"我先想清楚需要两级阈值"。

#### 证据 3: **`containsTargets` 字段是踩雷才有的**

设计初期一定是这样:

```typescript
// 版本 1
if (node.matches(TableSignature)) candidates.push('Table');
if (node.matches(RowSignature)) candidates.push('Row');
```

**然后线上出问题**:
- Table 里的每行都被识别为 Row
- LLM 拿到一堆重复候选, 生成代码乱七八糟
- **加字段**: `containsTargets: ['Row']`

**这个字段的存在本身就是"事故驱动设计"的证据**。

#### 证据 4: **`applyContainmentRules` 里的"按深度排序" 是踩雷的补丁**

```typescript
const sorted = [...nodes].sort((l, r) => 
  getPathDepth(l.nodePath) - getPathDepth(r.nodePath)
);
```

**为什么按深度排序?** 不排序抑制会失效——**这个 bug 必须踩过一次才会写出这行**。设计阶段几乎不可能想到。

#### 证据 5: **`shouldScoreComponentCandidates` 的 skip 规则**

```typescript
if (nodeType === 'text') return false;
if (isDividerSvgSignal(node)) return true;
if (isSvgLikeComponentSignal(node)) return false;
```

**每一行都是"避免踩坑"**:
- TEXT 跳过 → 之前误判过某个 TEXT 是 Button
- Divider 特殊放行 → SVG-like 一般跳过, 但 Divider 是特例

**不是预先设计的过滤, 是踩了一遍所有坑后的排除清单**。

#### 证据 6: **签名里的 `ignoreSignals` 字段**

```typescript
{
  name: 'Button',
  ignoreSignals: ['question icon', 'dropdown arrow when only used as signal'],
}
```

`ignoreSignals` 的存在本身说明——**"发现误判 → 加特殊排除"的产物**。设计阶段不会预先知道有哪些误报, 只能上线后收集。

### 那到底哪些是"设计"的, 哪些是"积累"的?

#### 能设计的层 (架构骨架)

**整体架构**: 打分 + 抑制 + 两级阈值 + adapter

这是**经典专家系统模式**, 编译器 / NLP 分词 / OCR 里都用过几十年:
- 词法分析: token 打分 + 冲突消解
- NLP 分词: 词频打分 + 最大匹配抑制
- OCR: 字符识别打分 + 形近字消歧

**熟悉这些领域的工程师能想到"打分 + 抑制"的架构**——但**只是骨架**。

#### 只能积累的层 (规则库)

**3364 行签名 + 20+ 条强信号 + 各种 skip/ignore 规则**

**没有任何工程师能一次性写出这 3364 行**。它必须来自:
- 每次识别失败 → 加规则
- 每次误报 → 加抑制
- 每次线上 bug → 补 signature

**大概率迭代过程**:
```
第 1 周: 有个 Button 签名, 只用 nameHints
第 2 周: 漏掉了 AI Button (Figma 命名不一样) → 加 componentNameHints
第 3 周: 漏掉自定义按钮 (子节点特殊) → 加 childNameHints  
第 4 周: 假阳性 (Popover 里的按钮被识别成外层 Button) → 加 containsTargets
第 5 周: AI Button 强信号 → 加强信号覆写
...
第 N 周: 3364 行签名成型
```

**这不是设计的, 是熬出来的**。

### 团队规模推测

| 观察 | 推测 |
|---|---|
| 3364 行 signature 库 | 至少 **6 个月**积累 |
| 20+ 强信号覆写规则 | 至少 **20 次线上事故**驱动 |
| 5 个 tool 完整生态 | 至少 **2-3 人**的核心开发团队 |
| 有 hiui / m4b 双设计系统适配 | 说明团队至少支持过一次"横向复制" |
| 有 debug/主两级阈值 | 说明有**运营/回归测试**机制 |
| 有 CoCo Sandbox 多轮迭代 | 说明团队投入了**评测集 + 反馈闭环** |

**推测**: **3-5 人核心团队, 花了 6-12 个月演化到当前状态**。

### 类比: 编译器发展史

**GCC (GNU 编译器) 的历史很类似**:
- **整体架构**: 词法/语法/语义分析 —— **设计出来的** (龙书里就有)
- **具体规则**: 优化规则 30 年积累了几万条 —— **踩坑积累的**
- **每条优化都对应一个具体的性能问题**

**这个 D2C 系统就是"Figma 领域的 mini 编译器"** —— 骨架是设计的, 规则是踩坑的。

### 好设计的两种流派

#### 流派 A: **"设计先行" (Top-down)**
- 先想清楚架构再写代码
- 一次设计, 长期使用
- 例子: SQL / TCP/IP / Java 集合框架

#### 流派 B: **"演化涌现" (Emergent)**
- 从小规模开始, 边用边改
- 每次事故是学习机会
- 例子: Linux kernel / GCC / 大部分互联网系统

**这个 D2C 系统属于流派 B**——**没人能预见"Figma 里 tag input 长这样"、"AI Button 有特殊命名"**。**只能上线一版, 收集反馈, 迭代**。

### 最深的洞察: **规则库本身就是护城河**

**这也是这个系统的价值所在**——**规则库不可复制**。

- 就算把源码全给竞争对手, 他们没有那 6 个月的踩坑数据, 也做不出同样的效果
- **签名规则本身就是"知识资产"**
- **不是那 632 行工厂代码, 是那 3364 行签名规则里凝结的领域知识**

### 一句话回答"人能想出来吗"

> **能, 但不是"设计"出来的, 是"踩坑积累"出来的**。整体架构 (打分 + 抑制 + 两级阈值 + adapter) 是有经验的架构师能设计的, **但 3364 行具体签名 + 20+ 强信号覆写 + 各种 skip 规则, 只能靠 6-12 个月的生产迭代积累**。**代码里到处都是"疤痕" (奇怪的数字、异常分支、强信号补丁), 反而说明它是真实生产系统, 不是纸上设计**。

### 一个更深的洞察: AI 应用真正的护城河

**很多人以为"AI 应用 = 调 LLM"**, 但这个 D2C 系统告诉你: **真正的 AI 应用 = 大量的"规则积累" + 一层薄薄的 LLM**。

- **LLM 是杠杆**, 但没有规则支撑, 杠杆撬不起东西
- **规则库是护城河**, 但没有 LLM, 规则再多也是死的
- **两者结合**, 才能做出真正有价值的产品

**这也是为什么"AI 应用产品化"这么难**——**你需要真实的用户和真实的数据积累**才能建立起规则库。**光靠开源 LLM 复刻不出这种系统**。

**规则库 = 从用户真实使用中蒸馏出来的"暗知识"** —— 是真正的技术壁垒。

---

## 15. adapter 的传递机制: context propagation

### 直接答案

**adapter 不是"注册到全局", 是"通过 `context` 参数手动传递"**。

- 不是全局变量
- 不是依赖注入容器
- 不是"注册到某处"

**就是普通的 JS 函数参数**——**从工厂 execute 传给内部 tool 的 execute**。

### 关键 3 行代码

如果只记住 3 行代码, 就是这 3 行:

**L484-497 (`create-figma-to-design-system-tool.ts` 工厂里)**:

```typescript
await getFigmaNodeDataTools.execute!(
  input,
  { ...context, designSystemAdapter: adapter },  // ★ 这就是 adapter 传递机制
);
```

**L2617 (`get-figma-node.ts` 内部 tool 里)**:

```typescript
const designSystemAdapter = getDesignSystemAdapterFromContext(context);
```

**L38-43 (`get-figma-node.ts` fallback)**:

```typescript
function getDesignSystemAdapterFromContext(context) {
  return context?.designSystemAdapter ?? m4bDesignSystemAdapter;
  //                                       ^^^^^^^^^^^^^^^^^^^^^
  //                                       忘了传就走默认 m4b
}
```

### 完整传递链 (逐层追)

```
第 1 层: 工厂 execute 拿到 adapter
─────────────────────────
createFigmaToDesignSystemTool({
  adapter: m4bDesignSystemAdapter,   ← 工厂配置时传入
})
→ 工厂函数内部形成闭包, adapter 变量被捕获
                              │
                              ▼
第 2 层: MCP 调用触发 execute
─────────────────────────
execute: async ({ context }) => {
  // context 是 MCP 层传来的原始上下文 (tracingContext 等)
  // adapter 是从闭包拿的
}
                              │
                              │ execute 内部调 getFigmaNodeDataTools
                              ▼
第 3 层: ★ 关键的 context 增强
─────────────────────────
await getFigmaNodeDataTools.execute!(
  inputData,
  {
    ...context,                    // 展开原始 context
    designSystemAdapter: adapter,   ★ 塞进 adapter!
  }
);
→ 增强版 context 传给下一个 tool
                              │
                              ▼
第 4 层: 内部 tool 从 context 拿 adapter
─────────────────────────
execute: async ({ context }) => {
  // L2617: 从 context 里拿 adapter
  const adapter = getDesignSystemAdapterFromContext(context);
  
  // L2624: 调用 adapter 的方法
  const candidateDetectionResult = 
    adapter.detectComponentCandidates(simplifiedDesign);
}
```

### 修正 3 个常见误解

#### 误解 1: **"注册到全局"**

**误解**: "通过 context 将工具注册到全局"

**实际**: **不是注册, 是"手动传参"**。

```typescript
// ❌ "注册到全局" 长这样 (不是这个实现)
globalContext.set('designSystemAdapter', m4bAdapter);
// 别的地方: globalContext.get('designSystemAdapter')

// ✅ 实际实现 (手动传参)
await innerTool.execute(input, { ...context, designSystemAdapter: adapter });
//                                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
//                                            每次调用都手动传, 不是"注册"
```

**关键差异**:
- **注册到全局**: 一次注册, 到处能用
- **手动传参**: 每次调用都要**显式传递**

#### 误解 2: **"context 是特殊容器"**

**误解**: context 是 Mastra 提供的"特殊依赖注入容器"

**实际**: **context 就是一个普通 JS 对象**, 没有魔法。

```typescript
{
  // MCP 层原本提供的字段
  tracingContext: { currentSpan: ... },
  mastra: { getAgentById: ... },
  
  // 工厂手动塞进去的字段
  designSystemAdapter: m4bAdapter,
}
```

**就是一个 plain object**。**Mastra 不做任何特殊处理**——只是把这个对象作为参数传给 execute。你要往里塞什么字段, **就是往 JS 对象上加属性**。

#### 误解 3: **"adapter 会自动透传到所有子调用"**

**误解**: adapter 一旦挂到 context, 所有下游都能拿到

**实际**: **每一层都要"手动塞"**, 否则下一层拿不到。

```typescript
// 调 getFigmaMetricsTool 时
await getFigmaMetricsTool.execute(input, {
  ...context,
  designSystemAdapter: adapter,  // ← 必须手动塞
});

// 调 getFigmaNodeDataTools 时  
await getFigmaNodeDataTools.execute(input, {
  ...context,
  designSystemAdapter: adapter,  // ← 又要塞一次
});
```

**如果哪一层忘了塞**, 下一层就拿不到 adapter, 会 fallback 到默认值 `m4bDesignSystemAdapter`。

### 这个模式的正式名称: **"Context Propagation" (上下文传播)**

**特点**:
- **显式传递** — 每层都要主动传, 不能自动"透传"
- **可增量** — 每层可以往 context 里加字段
- **无副作用** — 不改变全局状态, 只在本次调用链有效
- **隔离** — 不同请求的 context 互不影响

### 类比: 接力赛的接力棒

```
第 1 棒运动员 (工厂)
    │ 拿到接力棒 (adapter)
    │ 跑一段
    │ 传给下一棒
    ▼
第 2 棒运动员 (getFigmaNodeDataTools)
    │ 从上一棒接过棒子
    │ 跑一段
    │ 使用棒子调 adapter.detectComponentCandidates
    ▼
第 3 棒运动员 (具体规则算法)
    │ 使用棒子
```

**接力棒 = adapter**
**接力 = context 参数传递**
**掉棒 = 忘了传, 下一棒拿不到 → fallback 默认**

**vs 全局注册 (反面类比)**:
```
所有运动员共享一个"补给箱"
任何时候从箱子里拿 adapter
```

**差异**:
- 接力: 显式、按次传递、可以中途换
- 全局补给箱: 隐式、一次注册永久有效

### 为什么不用"全局注册"?

#### 原因 1: **同进程可能同时处理 m4b 和 hiui**

一个 FaaS 实例可能同时收到两个请求:
- 请求 A: 走 m4b adapter
- 请求 B: 走 hiui adapter

**如果 adapter 是全局注册**, 就会互相污染 (请求 A 的中途, 请求 B 覆盖了 adapter)。

**context 传递** 天然请求隔离——每个请求有自己的 context, 互不影响。

#### 原因 2: **可测试**

```typescript
// 测试时能轻松替换 adapter
await getFigmaNodeDataTools.execute(input, {
  designSystemAdapter: mockAdapter,  // ← 注入 mock
});
```

**如果是全局注册, 测试时得先 set 再调用, 麻烦且危险**。

#### 原因 3: **符合 Mastra Tool 的接口契约**

Mastra Tool 的 execute 签名就是 `(input, context) => output` —— **context 是一等公民参数**, 不是"外部读取"。所有传递都通过参数, 保持函数式纯度。

### adapter 的完整生命周期

```
[部署时]
    m4b Adapter 定义在 m4b/core/adapter.ts (静态导出)
    → const m4bDesignSystemAdapter = { ... }

[启动时]
    figma-to-m4b.ts 调工厂, 传入 adapter:
    → createFigmaToDesignSystemTool({ adapter: m4bDesignSystemAdapter })
    → 工厂内部形成闭包, adapter 变量被捕获

[请求时]
    用户从 Codex 调 figmaToM4bComponents
    → MCP server 收到请求
    → 调 tool.execute(input, context)
    → 工厂的 execute 函数开始运行
    → 从闭包拿 adapter (第 1 次拿)
    → 调 getFigmaNodeDataTools.execute(input, { ...context, designSystemAdapter: adapter })
    → 内层 execute 从 context 拿 adapter (第 2 次拿)
    → adapter.detectComponentCandidates(...) (第 3 次拿, 使用)

[请求结束]
    context 对象销毁 (GC)
    adapter 单例在闭包里, 等下一次请求
```

**adapter 是"闭包变量 + context 参数"的组合传递**——**永远在函数调用栈内**, 从不进入"全局作用域"。

### 一句话总结

> **adapter 不是"注册到全局", 是"通过 context 参数手动传递"**。工厂在配置时通过闭包捕获 adapter, 在调用内部 tool 时**手动把 adapter 塞入 context** (`{ ...context, designSystemAdapter: adapter }`), 内部 tool 从 context 里读取。**这是 "context propagation" 模式, 不是"依赖注入容器"**——每一层都显式传递, 不透传, 请求间隔离, 天然支持测试和多设计系统并发。
