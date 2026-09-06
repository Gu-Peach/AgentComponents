# VC Simulation Backend

当前后端阶段只实现基础业务能力，不包含 Agent、LLM 调用或复杂编排。

## 本地启动

```powershell
cd backend
python -m pip install -r requirements.txt
Copy-Item .env.example .env
supabase start
docker compose up -d redis
python -m app.db.init_db
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Supabase 本地服务端口已避开仓库中其它本地项目：API `55421`、Postgres `55422`、Studio `55423`、Mailpit `55424`、Analytics `55427`。Redis 暴露在 `6380`，容器内仍为 `6379`；数据卷绑定到 `backend/.local/redis`，避免把缓存数据写入 C 盘项目外路径。

## 当前 API 范围

- `GET /health`
- `POST /api/projects`、`GET /api/projects`、`GET /api/projects/{project_id}`
- `GET /api/projects/{project_id}/scene`
- `POST/PATCH/DELETE /api/projects/{project_id}/scene/instances...`
- `GET/POST/DELETE /api/projects/{project_id}/scene/{process|physical|signal}-edges...`
- `POST /api/projects/{project_id}/interfaces/compile`
- `POST /api/projects/{project_id}/topology/rebuild`、`GET /api/projects/{project_id}/topology`、`GET /api/projects/{project_id}/topology/reachability`
- `GET/POST /api/device-specs`、`GET /api/device-specs/{spec_id}`、`POST /api/device-specs/import-defaults`
- `GET/POST /api/assets`、`GET /api/assets/{asset_id}`
- `POST /api/projects/{project_id}/simulation-runs`、`GET /api/simulation-runs/{run_id}`
- `GET/PUT/DELETE /api/simulation-runs/{run_id}/runtime-snapshot`
- `POST /api/simulation-runs/{run_id}/signals/{signal_id}/emit`
