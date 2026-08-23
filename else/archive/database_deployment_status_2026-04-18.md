# 本地数据库部署结果归档（2026-04-18）

## 1. 背景

项目设计文档中规划的本地基础设施为：

- PostgreSQL
- MongoDB
- Redis
- MinIO

对应设计参考：

- [数据库架构说明](../design/database/README.md)
- [文档中心总览](../README.md)

## 2. 本次排查结论

2026-04-18 本地 Docker 环境检查结果如下：

### 2.1 项目计划中的四个服务

已存在以下容器：

- `behavior-postgres`
- `behavior-mongodb`
- `behavior-redis`
- `behavior-minio`

初始状态为：

- 4 个容器都已创建，但当时处于 `Exited` 状态
- 对应端口 `5432`、`27017`、`6379`、`9000` 均不可连通

切换后状态为：

- 已停止全部 `supabase_*` 相关运行容器
- 已启动 `behavior-postgres / behavior-mongodb / behavior-redis / behavior-minio`
- 4 个容器状态均为 `Up (...) (healthy)`
- 对应端口均已通过本机 TCP 连通性检查

### 2.2 Supabase 相关情况

本机此前还存在一组 Supabase 容器，例如：

- `supabase_db_gptwin`
- `supabase_studio_gptwin`
- `supabase_storage_gptwin`
- `supabase_realtime_gptwin`
- `supabase_auth_gptwin`

这组容器在排查开始时处于运行中，开放的主要是 Supabase 自己的端口（如 `54321`、`54322`、`54323`），并不等同于项目当前规划中直接使用的 4 个基础服务。

因此本次处理选择：

- 停止 Supabase 相关容器
- 切换为直接使用项目规划的 PostgreSQL / MongoDB / Redis / MinIO

## 3. 当前本地连接信息

当前应使用以下本地地址：

| 服务 | 容器名 | 地址 |
|---|---|---|
| PostgreSQL | `behavior-postgres` | `localhost:5432` |
| MongoDB | `behavior-mongodb` | `localhost:27017` |
| Redis | `behavior-redis` | `localhost:6379` |
| MinIO API | `behavior-minio` | `localhost:9000` |
| MinIO Console | `behavior-minio` | `localhost:9001` |

### 3.1 MinIO 登录信息

当前 `behavior-minio` 容器配置的账号密码为：

- 用户名：`behavior_user`
- 密码：`behavior_pass`

浏览器访问地址：

- `http://localhost:9001`

### 3.2 图形化管理界面

已在仓库根目录的 [docker-compose.yml](/e:/project/Agentic%20Components/docker-compose.yml) 中补充以下管理界面服务：

| 数据服务 | 管理界面 | 容器名 | 浏览器地址 | 登录信息 |
|---|---|---|---|---|
| PostgreSQL | pgAdmin | `behavior-pgadmin` | `http://localhost:5050` | 邮箱 `admin@behavior.dev` / 密码 `behavior_pass` |
| MongoDB | Mongo Express | `behavior-mongo-express` | `http://localhost:8081` | 用户名 `admin` / 密码 `behavior_pass` |
| Redis | Redis Commander | `behavior-redis-commander` | `http://localhost:8082` | 用户名 `admin` / 密码 `behavior_pass` |

说明：

- pgAdmin 已预置 PostgreSQL 连接项，连接文件位于 [database/admin/pgadmin/servers.json](/e:/project/Agentic%20Components/database/admin/pgadmin/servers.json)
- pgAdmin 首次连接 PostgreSQL 时，仍可能需要输入数据库密码：`behavior_pass`
- Mongo Express 已预配置连接 `behavior-mongodb`
- Redis Commander 已预配置连接 `behavior-redis`

各服务账号说明：

- pgAdmin 界面登录：邮箱 `admin@behavior.dev`，密码 `behavior_pass`
- PostgreSQL 数据库登录：用户名 `behavior_user`，密码 `behavior_pass`
- Mongo Express 界面登录：用户名 `admin`，密码 `behavior_pass`
- MongoDB 数据库登录：用户名 `behavior_user`，密码 `behavior_pass`
- Redis Commander 界面登录：用户名 `admin`，密码 `behavior_pass`
- Redis 服务认证密码：`behavior_pass`

### 3.3 管理界面启动结果

已执行启动命令：

```powershell
docker compose up -d --no-deps pgadmin mongo-express redis-commander
```

当前已成功启动的管理界面及端口：

- PostgreSQL 管理界面 `pgAdmin`：`http://localhost:5050`
- MongoDB 管理界面 `Mongo Express`：`http://localhost:8081`
- Redis 管理界面 `Redis Commander`：`http://localhost:8082`

对应登录信息：

- `http://localhost:5050` -> 邮箱 `admin@behavior.dev` / 密码 `behavior_pass`
- `http://localhost:8081` -> 用户名 `admin` / 密码 `behavior_pass`
- `http://localhost:8082` -> 用户名 `admin` / 密码 `behavior_pass`

## 4. 查看方式

以下命令均可在 PowerShell 中执行。

### 4.1 查看容器是否在运行

```powershell
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
```

若只想看项目计划中的 4 个服务，可重点确认是否存在：

- `behavior-postgres`
- `behavior-mongodb`
- `behavior-redis`
- `behavior-minio`

### 4.2 查看所有容器，包括已退出容器

```powershell
docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
```

这个命令适合排查“容器是否部署过但没有运行”。

### 4.3 查看本机端口是否真的可连

```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 5432
Test-NetConnection -ComputerName 127.0.0.1 -Port 27017
Test-NetConnection -ComputerName 127.0.0.1 -Port 6379
Test-NetConnection -ComputerName 127.0.0.1 -Port 9000
```

判断标准：

- `TcpTestSucceeded : True` 表示该服务端口已可连接
- `TcpTestSucceeded : False` 表示服务未运行、端口未映射，或启动异常

### 4.4 查看镜像是否已经拉取

```powershell
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.ID}}"
```

本机已确认存在以下相关镜像：

- `postgres:16-alpine`
- `mongo:7.0`
- `redis:7-alpine`
- `minio/minio:latest`

## 5. 常用切换命令

### 5.1 停止所有运行中的 Supabase 容器

```powershell
$names = docker ps --filter "name=^supabase_" --format "{{.Names}}"
if ($names) {
  $names | ForEach-Object { docker stop $_ }
}
```

### 5.2 启动项目计划中的四个数据库服务

```powershell
docker start behavior-postgres behavior-mongodb behavior-redis behavior-minio
```

### 5.3 如果需要再次停止这四个服务

```powershell
docker stop behavior-postgres behavior-mongodb behavior-redis behavior-minio
```

## 6. 本次实际验证结果

本次已实际验证通过：

- `behavior-postgres` 运行正常，`5432` 可连
- `behavior-mongodb` 运行正常，`27017` 可连
- `behavior-redis` 运行正常，`6379` 可连
- `behavior-minio` 运行正常，`9000` 可连

说明当前本机已经可以按照项目规划，直接使用这 4 个基础服务进行开发和联调。

## 7. 后续建议

- 将项目 `.env` 或后端配置统一指向上述 4 个本地端口
- 若后续重新启用 Supabase，请避免与现有本地端口和容器职责混用
- 若容器再次出现 `Exited`，优先使用 `docker ps -a` 和 `docker logs <容器名>` 排查
