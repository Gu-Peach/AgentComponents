# OAuth 2.0 登录流程说明

## 1. 文档目的

这份文档解释当前项目里已经落地的这条登录链路：

`浏览器点击 GitHub/Google 登录 -> Auth.js/NextAuth 完成第三方 OAuth -> 前端服务端调用后端换票 -> 后端写入用户/OAuth 账号/refresh token -> 返回系统自己的 access token / refresh token`

重点回答下面几个问题：

- 是哪个文件、哪个函数先发起请求
- 每一步发了什么
- 后端怎么处理
- 返回了什么
- `.env` 里每个配置的作用是什么

---

## 2. 当前架构中的角色分工

### 2.1 前端（Next.js + Auth.js）

前端负责两件事：

1. 和第三方 OAuth provider 交互
2. 在第三方登录成功后，把 provider 返回的用户资料和 token 元数据发给后端，换取系统自己的双 Token

### 2.2 后端（FastAPI）

后端负责三件事：

1. 将第三方 OAuth 身份落库到 `users` / `oauth_accounts`
2. 生成系统自己的 `access_token`
3. 生成并持久化系统自己的 `refresh_token`

### 2.3 第三方 OAuth Provider

当前支持：

- GitHub
- Google

它们负责：

- 用户授权
- 返回 provider 自己的用户身份和 token 信息

---

## 3. 总体流程图

```text
浏览器
  -> 点击登录按钮
  -> /api/auth/signin/github or /api/auth/signin/google

NextAuth
  -> 跳转到 GitHub / Google 授权页
  -> 用户完成授权
  -> provider 回调到 /api/auth/callback/{provider}
  -> 进入 authOptions.callbacks.jwt()

frontend/lib/auth.ts
  -> 调用 exchangeOAuthLogin()
  -> POST http://localhost:8000/api/auth/oauth/exchange

FastAPI backend
  -> 校验 X-Auth-Bridge-Secret
  -> upsert users / oauth_accounts
  -> 生成 access_token
  -> 生成 refresh_token 并写入 refresh_tokens
  -> 返回 token pair + user

NextAuth
  -> 将后端返回的 token 写入自己的 JWT/session
  -> 服务端页面根据 session.appAccessToken 判断登录态
```

---

## 4. 前端登录发起阶段

### 4.1 按钮点击来自哪里

文件：

- `frontend/components/auth/OAuthLoginButtons.tsx`

关键函数：

- `onClick={() => signIn(provider.id, { callbackUrl })}`

也就是这里：

```tsx
onClick={() => signIn(provider.id, { callbackUrl })}
```

当用户点击：

- `使用 GitHub 登录`
- `使用 Google 登录`

实际上调用的是 `next-auth/react` 的 `signIn()`。

### 4.2 这一层发送了什么

`signIn('github', { callbackUrl: '/projects' })` 或 `signIn('google', { callbackUrl: '/projects' })`

它不是直接发给后端，而是先走 Auth.js 自己的路由：

- `/api/auth/signin/github`
- `/api/auth/signin/google`

对应的 route 文件是：

- `frontend/app/api/auth/[...nextauth]/route.ts`

这里的核心是：

```ts
const handler = NextAuth(authOptions);
export { handler as GET, handler as POST };
```

说明真正处理登录的是 `NextAuth(authOptions)`。

---

## 5. Auth.js / NextAuth 处理第三方 OAuth

### 5.1 Provider 配置在哪里

文件：

- `frontend/lib/auth.ts`

关键位置：

- `GitHubProvider(...)`
- `GoogleProvider(...)`
- `authOptions`

这里根据环境变量决定是否启用 provider：

```ts
if (process.env.AUTH_GITHUB_ID && process.env.AUTH_GITHUB_SECRET) {
  providers.push(GitHubProvider(...))
}
```

```ts
if (process.env.AUTH_GOOGLE_ID && process.env.AUTH_GOOGLE_SECRET) {
  providers.push(GoogleProvider(...))
}
```

### 5.2 第三方登录成功后进入哪个函数

核心入口是：

- `frontend/lib/auth.ts`
- `authOptions.callbacks.jwt`

关键函数：

```ts
async jwt({ token, account, profile }) { ... }
```

当 `account` 存在时，说明这是一次新的 provider 登录成功回调。

这时会先把第三方返回的信息写到 NextAuth token 中：

```ts
token.provider = account.provider;
token.providerAccessToken = account.access_token;
token.providerRefreshToken = account.refresh_token;
token.providerAccessTokenExpiresAt = account.expires_at
  ? account.expires_at * 1000
  : undefined;
```

然后立刻调用：

```ts
const backendSession = await exchangeOAuthLogin(...)
```

---

## 6. 前端向后端换票

### 6.1 是哪个函数发请求

文件：

- `frontend/lib/backend-auth.ts`

函数：

- `exchangeOAuthLogin(params)`

### 6.2 请求发到哪里

```text
POST {BACKEND_API_URL}/api/auth/oauth/exchange
```

默认就是：

```text
POST http://localhost:8000/api/auth/oauth/exchange
```

### 6.3 带了什么请求头

```ts
headers: {
  'Content-Type': 'application/json',
  'X-Auth-Bridge-Secret': bridgeSecret,
}
```

其中最关键的是：

- `X-Auth-Bridge-Secret`

这个值来自：

- `frontend/.env.local` 中的 `AUTH_BRIDGE_SECRET`

它的作用是让后端确认：

- 这次换票请求是我们自己的前端服务端发来的
- 不是外部伪造请求

### 6.4 请求体发送了什么

请求体结构来自：

- `frontend/lib/backend-auth.ts`
- `exchangeOAuthLogin()`

发送内容如下：

```json
{
  "provider": "github",
  "provider_user_id": "provider-user-id",
  "email": "user@example.com",
  "display_name": "User Name",
  "avatar_url": "https://...",
  "access_token": "provider-access-token",
  "refresh_token": "provider-refresh-token",
  "token_type": "bearer",
  "scope": "read:user user:email",
  "id_token": null,
  "expires_at": "2026-04-19T08:00:00.000Z"
}
```

说明：

- `provider_user_id` 来自 GitHub/Google 的用户唯一标识
- `access_token` / `refresh_token` 是 provider 自己的 token，不是我们系统的 token
- `expires_at` 是 provider access token 的过期时间

---

## 7. 后端如何处理 `/api/auth/oauth/exchange`

### 7.1 路由入口

文件：

- `backend/api/auth.py`

函数：

- `exchange_oauth_login(...)`

关键逻辑：

```python
@router.post("/oauth/exchange")
async def exchange_oauth_login(...):
    service = AuthService(session)
    return await service.exchange_oauth_login(...)
```

### 7.2 先做什么校验

在路由参数里有：

```python
_: None = Depends(require_bridge_secret)
```

也就是说先执行：

- `backend/dependencies.py`
- `require_bridge_secret()`

它会读取请求头：

- `X-Auth-Bridge-Secret`

并和后端环境变量里的：

- `AUTH_BRIDGE_SECRET`

做比对。

如果不一致，后端直接返回 `401`。

### 7.3 业务处理在哪个函数

文件：

- `backend/services/auth_service.py`

函数：

- `AuthService.exchange_oauth_login(...)`

这个函数主要分 4 步。

#### 第 1 步：查 `oauth_accounts`

```python
account = await self.repository.get_oauth_account(
    payload.provider,
    payload.provider_user_id,
)
```

如果这个 provider 身份已经绑定过系统用户，就直接找到对应的 `user`。

#### 第 2 步：创建或更新 `users`

如果 `oauth_accounts` 里没有，就按 email 查 `users`：

```python
user = await self.repository.get_user_by_email(resolved_email)
```

如果找不到，就创建一个新用户：

```python
User(
    email=resolved_email,
    display_name=...,
    avatar_url=...,
    email_verified_at=...,
    status="ACTIVE",
    last_login_at=now,
)
```

#### 第 3 步：创建或更新 `oauth_accounts`

如果这次 provider 身份第一次出现，就插入：

```python
OAuthAccount(
    user_id=user.id,
    provider=payload.provider,
    provider_user_id=payload.provider_user_id,
    provider_email=payload.email,
    scope=payload.scope,
    token_type=payload.token_type,
    access_token=payload.access_token,
    refresh_token=payload.refresh_token,
    id_token=payload.id_token,
    expires_at=payload.expires_at,
)
```

如果这个 provider 身份已经存在，就更新这些字段。

#### 第 4 步：签发系统自己的双 Token

调用：

```python
token_response = await self._issue_token_pair(...)
```

---

## 8. 后端如何生成 access token / refresh token

### 8.1 `access token`

文件：

- `backend/core/auth.py`

函数：

- `create_access_token(subject, email, provider)`

生成的 JWT payload 类似：

```json
{
  "sub": "user-id",
  "email": "user@example.com",
  "provider": "github",
  "type": "access",
  "exp": "...",
  "iat": "..."
}
```

它使用：

- `JWT_SECRET`
- `JWT_ALGORITHM`

进行签名。

### 8.2 `refresh token`

文件：

- `backend/core/auth.py`

函数：

- `generate_refresh_token()`
- `hash_refresh_token(token)`

逻辑是：

1. 先生成随机字符串 refresh token
2. 再对 refresh token 做 SHA-256
3. 只把 hash 后的结果写入数据库

数据库表：

- `refresh_tokens`

也就是说数据库里不会明文保存 refresh token。

### 8.3 `refresh_tokens` 表里写了什么

文件：

- `backend/services/auth_service.py`
- `_issue_token_pair(...)`

写入内容包括：

- `user_id`
- `token_hash`
- `family_id`
- `user_agent`
- `ip_address`
- `expires_at`

---

## 9. 后端返回给前端什么

后端响应模型：

- `backend/schemas/auth.py`
- `AccessTokenPairResponse`

返回结构：

```json
{
  "access_token": "our-app-access-token",
  "refresh_token": "our-app-refresh-token",
  "token_type": "Bearer",
  "expires_in": 900,
  "refresh_expires_at": "2026-05-03T07:42:03.436287Z",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "display_name": "User Name",
    "avatar_url": "https://...",
    "status": "ACTIVE"
  }
}
```

说明：

- `access_token` / `refresh_token` 从这一刻起已经是“系统自己的 token”
- 后续业务接口认证应该使用这个 `access_token`

---

## 10. 前端拿到后端 token 后怎么处理

### 10.1 写入 NextAuth token

文件：

- `frontend/lib/auth.ts`
- `authOptions.callbacks.jwt`

在 `backendSession` 成功返回后，写入：

```ts
token.appAccessToken = backendSession.accessToken;
token.appRefreshToken = backendSession.refreshToken;
token.appAccessTokenExpiresAt = backendSession.accessTokenExpiresAt;
token.appRefreshTokenExpiresAt = backendSession.refreshTokenExpiresAt;
token.appUserId = backendSession.user.id;
token.appUserEmail = backendSession.user.email;
token.appUserName = backendSession.user.name;
token.appUserImage = backendSession.user.image ?? undefined;
token.appUserStatus = backendSession.user.status;
```

### 10.2 再写到 session

同一个文件里的：

- `authOptions.callbacks.session`

把这些值暴露给页面：

```ts
session.appAccessToken
session.appRefreshToken
session.appAccessTokenExpiresAt
session.appRefreshTokenExpiresAt
session.authError
```

### 10.3 页面如何判断登录成功

当前页面保护逻辑依赖：

- `session.appAccessToken`

例如：

- `/`
- `/projects`
- `/workspace/[projectId]`

只有当 `session.appAccessToken` 存在时才认为用户真正进入系统。

这和“仅仅拿到 GitHub/Google session”是两回事。

---

## 11. refresh token 的处理流程

### 11.1 前端在哪触发刷新

文件：

- `frontend/lib/auth.ts`

函数：

- `authOptions.callbacks.jwt`

判断逻辑：

```ts
const accessTokenExpiresSoon =
  typeof token.appAccessTokenExpiresAt === 'number' &&
  Date.now() >= token.appAccessTokenExpiresAt - 30_000;
```

也就是：

- 如果系统自己的 access token 30 秒内要过期
- 并且存在 `appRefreshToken`

就调用：

```ts
refreshBackendAccessToken(token.appRefreshToken)
```

### 11.2 刷新请求发到哪里

文件：

- `frontend/lib/backend-auth.ts`

函数：

- `refreshBackendAccessToken(refreshToken)`

请求：

```text
POST {BACKEND_API_URL}/api/auth/refresh
```

请求体：

```json
{
  "refresh_token": "our-app-refresh-token"
}
```

### 11.3 后端如何处理刷新

文件：

- `backend/api/auth.py`
- `backend/services/auth_service.py`

入口函数：

- `refresh_access_token(...)`

逻辑：

1. 对传入的 refresh token 做 SHA-256
2. 查 `refresh_tokens.token_hash`
3. 检查是否存在、是否过期、是否已撤销
4. 找到对应用户
5. 重新签发一对新的 access token / refresh token
6. 将旧 refresh token 标记为 `revoked`
7. 将 `replaced_by_token_id` 指向新 token

这就是当前实现里的 refresh token 轮换机制。

---

## 12. `/api/auth/me` 是怎么工作的

文件：

- `backend/api/auth.py`

函数：

- `get_me(user=Depends(get_current_user))`

这里依赖：

- `backend/dependencies.py`
- `get_current_user()`

它会：

1. 从 `Authorization: Bearer <token>` 里取出 access token
2. 调用 `backend/core/auth.py` 的 `decode_access_token()`
3. 从 JWT 的 `sub` 中取用户 ID
4. 再查数据库拿到当前用户

返回的是：

- `CurrentUserResponse`

---

## 13. 环境变量说明

## 13.1 前端 `frontend/.env.local`

### `NEXTAUTH_URL`

示例：

```env
NEXTAUTH_URL=http://localhost:3000
```

作用：

- 告诉 Auth.js 当前应用自己的基础地址
- 用于生成回调 URL

### `NEXTAUTH_SECRET`

作用：

- 给 NextAuth 的 JWT / session / cookie 做签名和加密

### `BACKEND_API_URL`

示例：

```env
BACKEND_API_URL=http://localhost:8000
```

作用：

- 告诉前端服务端去哪个后端地址换系统 token

### `AUTH_BRIDGE_SECRET`

作用：

- 前端服务端调用 `/api/auth/oauth/exchange` 时附带在 `X-Auth-Bridge-Secret`
- 用来证明这是“我们自己的前端服务端”发来的换票请求

要求：

- 必须和 `backend/.env` 中的 `AUTH_BRIDGE_SECRET` 完全一致

### `AUTH_GITHUB_ID` / `AUTH_GITHUB_SECRET`

作用：

- GitHub OAuth App 的 client id / client secret
- 由 Auth.js 的 `GitHubProvider(...)` 使用

### `AUTH_GOOGLE_ID` / `AUTH_GOOGLE_SECRET`

作用：

- Google OAuth client id / client secret
- 由 Auth.js 的 `GoogleProvider(...)` 使用

---

## 13.2 后端 `backend/.env`

### `APP_NAME`

作用：

- FastAPI 应用名称

### `APP_ENV`

作用：

- 标识运行环境

### `API_HOST` / `API_PORT`

作用：

- 后端监听地址和端口

### `CORS_ORIGINS`

示例：

```env
CORS_ORIGINS=["http://localhost:3000"]
```

作用：

- 允许前端浏览器从哪些域跨域访问后端

注意：

- 这里必须写成 JSON 数组格式

### `POSTGRES_DSN`

作用：

- 后端连接 PostgreSQL 的 DSN

### `DB_AUTO_CREATE`

作用：

- 启动时是否自动创建 SQLAlchemy 已声明的表

### `JWT_SECRET`

作用：

- 给系统自己的 access token 做签名

### `JWT_ALGORITHM`

作用：

- 指定 JWT 算法，例如 `HS256`

### `ACCESS_TOKEN_TTL_MINUTES`

作用：

- 系统自己的 access token 有效期

### `REFRESH_TOKEN_TTL_DAYS`

作用：

- 系统自己的 refresh token 有效期

### `AUTH_BRIDGE_SECRET`

作用：

- 校验前端发来的 `X-Auth-Bridge-Secret`

要求：

- 必须和前端一致

---

## 14. 当前实现的边界

当前这版流程已经完成：

- 第三方 OAuth 登录
- 后端落库用户与 OAuth 账号
- 系统自己的双 Token 签发
- refresh token 轮换

但还没有做：

- 业务 API 全面切换到系统 access token
- logout / token 撤销接口
- 更完整的审计日志
- 更细的权限模型

也就是说，这条链路已经是可用的“认证主干”，但还不是最终的全量认证系统。
