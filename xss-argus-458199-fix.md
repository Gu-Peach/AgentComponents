# Argus XSS 工单修复复盘：dangerouslySetInnerHTML 净化实践

> 关联 Argus 工单：`[XSS 风险] 富文本渲染 - i18n_fe/sea_product_operation_next` assetId=458199
> 修复分支：`fix/xss-argus-ticket-458199`
> 修复范围：`apps/product` SPA subapp

## 一、背景

Argus 安全平台在本仓库扫描出 **5 处** XSS 风险，全部命中静态扫描规则 `javascript.DangerousHTML`。共同模式是"用户可控/i18n 可控的字符串数据未经净化，直接流入浏览器的 HTML 渲染 API"。

工单严重度：中危；DDL：2026-07-31；修复方式：接入 Argus 编译时安全插件（长期）或手动包裹 DOMPurify（短期）。

## 二、5 处命中点

### ① `apps/product/src/pages/skpp-program/components/empty-page/index.tsx:83:12`

```tsx
<div
  className="text-body-m-regular text-neutral-on-surface-strong mt-4"
  dangerouslySetInnerHTML={{
    __html: t('SKPP_no_product_page_content'),   // ← 未净化的 i18n 文案
  }}
/>
```

**风险数据源**：Starling i18n key。理论上有内控，但若后台被污染或运营误操作 → 恶意 HTML 直接在千万商家浏览器中执行。

### ②③④ `apps/product/src/widgets/preview/mode/product-desc/FormatHtmlImg.tsx:14/25/46`

`FormatHtmlImg` 把商品描述 HTML 拆开，`<img>` 换成 M4B `Image` 组件，其余文本段仍以 HTML 形式塞回。三处 `dangerouslySetInnerHTML` 分别对应：
- **:14** — 无 img 匹配时的整段渲染；
- **:25** — img 匹配之间的文本段切片；
- **:46** — 最后一个 img 之后的尾段。

**风险数据源**：`product.product_description` —— 商家自己在后台填写的富文本，**完全用户可控**。跨账号浏览商品预览时（比如 GPR 全球复制、后台 Preview 面板）可发起跨账号 XSS，是本次 5 处中**实际风险最高**的。

### ⑤ `apps/product/src/shared/utils/getHTMLText.ts:4:2`

```ts
export const getHTMLText = (HTML: string) => {
  const ele = document.createElement('div');
  ele.innerHTML = HTML;      // ← 命中：user-controlled → innerHTML
  return ele.innerText;
};
```

**特殊性**：detached div 上赋 `innerHTML` 在 HTML5 spec 下**不会真的执行 `<script>`**，也不会触发 `<img onerror>` 加载资源（节点未挂载）——**运行时无实际执行风险**。但 Argus 走静态污点分析，只看数据流是否流入危险 API，不看运行时语义，所以照样命中。

**唯一调用方**：`apps/product/src/pages/global-product-replicate/gpr-sync-page/modules/review-drawer/ReviewDrawer.tsx:354` —— GPR review drawer 里对 `product.product_description` 抽纯文本做省略号显示。

## 三、修复方案

采用**双方案组合**（不走 Argus 编译时插件，走"手动净化"路线）：

| 命中点 | 方案 | 工具 |
|---|---|---|
| ① empty-page | **净化 HTML** | `DOMPurify.sanitize()` |
| ② ③ ④ FormatHtmlImg | **净化 HTML** | `DOMPurify.sanitize()` |
| ⑤ getHTMLText | **提取纯文本** | `html-to-text` |

### 方案选型理由

**为什么不走 Argus 编译时插件（`@ies/argus-webpack-plugin`）**：
- 平台配置下发依赖 SCM 关联和 BUILD_REGION 支持，本仓库产物走 BundleSite（非 SCM 服务包），且 TikTok 业务 `BUILD_REGION=oci` 无法使用平台下发；
- 全走 SDK 硬编码配置，需修改 5 条 build pipeline，改动大、风险高；
- 项目里已有 20+ 处成熟的 `DOMPurify.sanitize()` 用法作为先例，走一致模式最省事。

**为什么第 5 处不用 `DOMPurify` 而用 `html-to-text`**：
- 该函数语义就是"从 HTML 抽取纯文本"，本来就不需要 HTML 渲染；
- 用 `html-to-text` 让整个数据链条从"HTML 世界"降级到"纯文本世界"——不再需要 DOM API，静态扫描规则从根本上不会命中；
- 项目里已有 `pages/listing/ai-listing/utils.ts` 用同一个库的先例，风格一致。

### 修改示例（前 4 处）

```diff
+ import DOMPurify from 'dompurify';

  <div
    dangerouslySetInnerHTML={{
-     __html: t('SKPP_no_product_page_content'),
+     __html: DOMPurify.sanitize(t('SKPP_no_product_page_content') ?? ''),
    }}
  />
```

`?? ''` 是防 `undefined` 让 sanitize 抛错。

### 修改示例（第 5 处）

```diff
- export const getHTMLText = (HTML: string) => {
-   const ele = document.createElement('div');
-   ele.innerHTML = HTML;
-   return ele.innerText;
- };
+ import { htmlToText } from 'html-to-text';
+
+ export const getHTMLText = (HTML: string) => {
+   return htmlToText(HTML, {
+     wordwrap: false,
+     selectors: [{ selector: 'img', format: 'skip' }],
+   });
+ };
```

`html-to-text` 已装（`html-to-text@9.0.5`），零新增依赖。

### 附带的类型声明修复

`html-to-text@9` 没自带 `.d.ts`，且项目未装 `@types/html-to-text`。在 `apps/product/src/types/global.d.ts` 补上模块声明：

```ts
declare module 'html-to-text';
```

顺带修好了原本 `pages/listing/ai-listing/utils.ts` 存在但被 IDE 增量检查漏掉的隐式 `any` 报错。

## 四、为什么这些做法能修复 XSS 风险

### 4.1 XSS 攻击链的本质

XSS 攻击的本质是：**攻击者把可执行的 JS 代码伪装成 HTML 内容，让浏览器把它当作页面内容执行**。触发 JS 执行的常见入口：

| 入口 | 例子 |
|---|---|
| `<script>` 标签 | `<script>alert(document.cookie)</script>` |
| 事件属性 | `<img src=x onerror=alert(1)>` |
| javascript: 协议 | `<a href="javascript:alert(1)">click</a>` |
| 内联样式表达式（老 IE） | `<div style="expression(alert(1))">` |
| SVG 里的脚本 | `<svg><script>...` |

只要"用户可控数据"能通过任意一种方式**变成 DOM 树里的可执行结构**，XSS 就成立。

### 4.2 DOMPurify.sanitize 的工作原理

`DOMPurify` 由 Cure53 团队维护，是当前浏览器端 XSS 防御的事实标准，被 OWASP 推荐。它做的事：

```
输入: '<b>hello</b><img src=x onerror=alert(1)><script>bad()</script>'
        ↓ DOMPurify.sanitize()
        ↓
        ├─ 步骤 1：把输入串成 DOM 树（内部使用浏览器解析器）
        ├─ 步骤 2：遍历每个节点，按"允许清单"过滤：
        │           - 标签白名单（<script> 不在里面 → 剥离）
        │           - 属性白名单（onerror 不在里面 → 剥离）
        │           - 协议白名单（javascript: 不在里面 → 剥离）
        │           - SVG/MathML 内嵌 script 特殊处理
        ├─ 步骤 3：处理 mXSS（mutation XSS）等浏览器 quirks
        └─ 步骤 4：把清理过的 DOM 树序列化回字符串
        ↓
输出: '<b>hello</b><img src="x">'
        ↓（作为 dangerouslySetInnerHTML 的输入）
浏览器渲染: 加粗的 "hello" + 一张（失败加载的）图，onerror 已被移除 → 无 JS 执行
```

**关键**：**不改变数据形态**（输入是 HTML 字符串，输出也是 HTML 字符串），但**内容更"干净"**。合法富文本（`<b>`、`<i>`、`<a>` 等）原样保留，恶意 payload 全被剥离。

**用在前 4 处的原因**：这些场景**需要**渲染富文本（要看到加粗、图片、超链接），不能降级为纯文本，只能"过滤"。

### 4.3 html-to-text 的工作原理

`html-to-text` 内部用 `htmlparser2`（纯 JavaScript 流式解析器）：

```
输入: '<b>hello</b><img src=x onerror=alert(1)>world'
        ↓ htmlparser2 词法分析
tokens: [tag(b), text(hello), tag(/b), tag(img), attr(src=x),
         attr(onerror=alert(1)), text(world)]
        ↓ html-to-text 按 selectors 规则处理：
        ├─ text tokens → 保留
        └─ tag tokens → 丢弃（不生成 DOM，不解析属性含义）
        ↓
输出: 'hello world'   ← 纯字符串
```

**关键差异（相比 DOMPurify）**：
- **全程不生成 DOM**，纯字符串处理；
- 输出**不再是 HTML**，是完全字符串；
- 后续调用方用 React `{}` 表达式渲染，React 自带 HTML 转义 —— 即便字符串意外包含 `<`、`>` 也当纯文本渲染，双保险。

**用在第 5 处的原因**：这个场景**本来就不需要**渲染 HTML，只要显示纯文本。用 `html-to-text` 直接把整条数据链从"HTML 世界"降级到"纯文本世界"，从根本上绕开了整个 XSS 攻击面。

### 4.4 为什么"包一层"能改变 Argus 判断

Argus 的静态扫描规则 `javascript.DangerousHTML` 大致逻辑：

```
识别 dangerouslySetInnerHTML / innerHTML = 等危险 API
    ↓
往上做污点分析（taint analysis），看数据源
    ↓
如果数据经过"已知安全净化函数"（白名单），标为已防御 → 不报警
否则报警
```

`DOMPurify.sanitize()`、`html-to-text()` 都在 Argus 的白名单里。所以你在数据流中间加一层安全 API，静态扫描就会自动"闭嘴"。**修复的不仅是运行时风险，也是扫描规则的形式合规**——两者需要同时满足。

## 五、遇到的坑与解决方式

### 5.1 Argus 权限申请

**问题**：Argus 上要关联 asset `458199`（对应本仓库）到自建项目时，提示"无权限"。虽然 Codebase 上有仓库的编辑权限，Argus 里却没有。

**根因**：Codebase 权限 ≠ Argus 权限，两套系统。Argus 的资产负责人是 `lixiang.0`、`gutao.123`，他们在 Argus 里独立维护 ACL。

**解法**：
1. 在 Argus 资产列表点该资产 → "申请权限" → 选**"资产编辑权限"**（不是"部门编辑权限"，部门权限过宽会被拒）；
2. 或直接找资产负责人授权。

### 5.2 Argus 里的 SCM 关联字段

**问题**：Argus 平台配置下发要求关联 SCM，但本项目查不到 SCM。

**根因**：SCM 是"服务侧发布位注册项"，`apps/product` 是纯前端 subapp，产物走 BundleSite（CDN），没有 SCM 注册项。

**解法**：不走平台配置下发，全部使用 SDK 硬编码配置。（但最终因为项目内已有 20+ 处 DOMPurify 先例，本次也没走 Argus 插件，走了手动方案。）

### 5.3 pnpm/node 版本冲突

**问题**：`apps/product/package.json` 的 `volta` 锁 pnpm 6.34 / node 16.20，但根 `package.json` 要求 pnpm 10.12.4 / node ≥22，且 `scm_build.sh` 也用 pnpm 10。

**解法**：以**根版本为准**——node 22 + pnpm 10.12.4。忽略 apps/product 的 volta 锁（历史技术债）。用 fnm 切 node、corepack 切 pnpm。

### 5.4 老 `dev:ppe` 脚本坏了

**问题**：`pnpm dev:ppe`（根脚本）展开是 `CUSTOM_DEVELOP_ENV=ONLINE pnpm dev --filter product`。里面的 `pnpm dev` 会命中根 `package.json` 的 `dev` 脚本（`pnpm --filter @shop/product-next dev`），最终跑起了 product-next（Vite 5173），而不是 apps/product。

**解法**：直接用精确 workspace 名 —— `pnpm --filter @shop/product run dev`，或者 `cd apps/product && pnpm run dev`。

### 5.5 本地 dev 编译报错 `NoDataElement not found`

**问题**：`pnpm run dev` 报 `Module not found: @/shared/adapters/packages/jupiter-runtime-i18n`。堆栈来自 `pages/sales-accelerator-new/`。

**根因**：`sales-accelerator-new` 是从 `business/` 反向同步到 `apps/product/` 的，但**同步不完整**——引用了 `shared/adapters/*` 但没有一起搬。这是 master 上就存在的脏状态，跟本次修复无关。

**解法**：本次采用 whistle 劫持 + 线上主宿主验证，不本地起完整 dev。也可以拷贝 `business/src/shared/adapters/` 到 `apps/product/src/shared/adapters/` 让本地编译通过（但拷不全，还要拷 `@atlas-kernel/i18n` 依赖，得不偿失）。

### 5.6 本地 SPA 不能独立跑

**问题**：dev server 起在 3103，但浏览器打开 `localhost:3103` 是空的。

**根因**：`apps/product` 是 Garfish subapp（"子壳"），入口 `subapp/index.tsx` 只导出 `provider()` 给主宿主调用，本身不挂载 React 到 DOM。本仓库不含主宿主代码（主宿主在其他 pearl 仓库），也没内置 mock shell。

**解法**：用 **Whistle 劫持** —— 让浏览器访问真实 seller-center（有登录态、主宿主、菜单、API），但线上 `product.js` 被劫持到本地 `127.0.0.1:3103/product.js`。项目 Whistle 有现成的 `product(subApp)` 规则组。

### 5.7 CI Pipeline HTTP 504 超时

**问题**：Bits pipeline 里 `TTP SCM 编译` 步骤挂了，报 `code=504, function_invoke_timeout`。

**根因**：CI 基建的云函数调用超时（5 分钟卡点），与代码无关。

**解法**：**点 Rerun 重试**。字节内部 CI 常见的临时抖动，重试大概率能过。

### 5.8 Bundle Size 分析报告的警告

**问题**：CI 附带 Bundle 分析报告，有 `Deduplicate versions of libraries`、`Uncontrolled libraries used in bundle result`、`Avoid cache wasting` 三类警告。

**根因**：项目历史技术债，与本次修复无关。本次 MR 只让 `IncubationProductsChart` chunk 缩小了 11KB，没引入任何新 bloat。

**解法**：忽略，非阻塞。

## 六、验证清单

- [x] `pnpm type-check` 通过
- [x] `pnpm lint` 通过
- [x] `[Pipeline] merge_request_build - build` 通过
- [x] `[Pipeline] lint&check - key-check` 通过
- [x] Whistle 劫持验证 SKPP 空态页文案正常显示
- [ ] Argus 复测（提交 MR 后等安全 BP 复测）

## 七、涉及的文件清单

| 文件 | 改动类型 |
|---|---|
| `apps/product/src/pages/skpp-program/components/empty-page/index.tsx` | 加 DOMPurify.sanitize |
| `apps/product/src/widgets/preview/mode/product-desc/FormatHtmlImg.tsx` | 加 DOMPurify.sanitize（3 处） |
| `apps/product/src/shared/utils/getHTMLText.ts` | 换用 html-to-text |
| `apps/product/src/types/global.d.ts` | 补 `declare module 'html-to-text';` |

## 八、后续可做的改进（不在本次范围）

1. **接入 Argus 编译时安全插件 `@ies/argus-webpack-plugin@3`**：一次性覆盖所有未来新增的 `dangerouslySetInnerHTML`，避免逐个手动包 DOMPurify。需要梳理 5 条 build pipeline 分别注入，且要处理 `BUILD_REGION=oci` 下平台配置不下发的兜底策略。
2. **统一 `getHTMLText` 与 `convertHtmlToText` 的实现**：项目里 `apps/product/src/shared/utils/getHTMLText.ts` 和 `apps/product/src/pages/listing/ai-listing/utils.ts` 都在做"HTML 抽文本"，可以合并到 `shared/utils` 中。
3. **清理 `sales-accelerator-new` 在 `apps/product/` 里的半吊子拷贝**：要么补全依赖让它能跑通，要么彻底移除、只保留在 `apps/product-next/` 里。
4. **修正根 `dev:ppe` 脚本**：把 `pnpm dev --filter product` 改成 `pnpm --filter @shop/product run dev`，避免误跑到 product-next。
5. **统一 `apps/product` 和根的 pnpm/node 版本要求**：删除 apps/product 里 volta 锁的老版本。

