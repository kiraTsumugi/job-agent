# Deployment Guide

按顺序执行。预估总耗时 30-60 分钟(首次),后续 redeploy 5 分钟内。

## 0. 前置准备

- GitHub 仓库(代码已 push)
- Railway 账号(https://railway.app)
- Vercel 账号(https://vercel.com)
- Qdrant Cloud 账号(https://cloud.qdrant.io,免费档 1GB)
- 已有的 DeepSeek API key + SiliconFlow API key

## 1. Qdrant Cloud(先做,因为要拿 URL + API key)

1. 登录 https://cloud.qdrant.io → Create Cluster → Free 1GB
2. 选 region(推荐 AWS Singapore,国内访问较快)
3. 创建后,记下:
   - **Cluster URL**:形如 `https://xxx-xxx.aws.cloud.qdrant.io:6333`
   - **API Key**:在 Dashboard → API Keys 生成

## 2. Railway 后端部署

### 2.1 创建项目

1. Railway Dashboard → **New Project** → **Deploy from GitHub repo**
2. 选你的仓库 → **Configure**(不要立即 deploy)

### 2.2 加 3 个数据服务

在同一个 Railway 项目里,**New → Database**:

- **PostgreSQL**:Railway 自动生成 `DATABASE_URL`(形如 `postgresql://...`),需要在末尾改成 `postgresql+asyncpg://...`(Railway 默认提供的变量在 Settings → Variables 里复制)
- **Redis**:Railway 自动生成 `REDIS_URL`

Qdrant 不在 Railway 上,用第 1 步的 Qdrant Cloud。

### 2.3 加后端 Web Service

1. Railway 项目里 **New → GitHub Repo**(同一个 repo)
2. **Settings**:
   - **Root Directory**:`/`(repo 根,因为 Dockerfile 在根)
   - **Build Command**:留空(Dockerfile 自动)
   - **Start Command**:留空(Dockerfile CMD)
   - Railway 会自动识别 Dockerfile
3. **Variables**(逐个填,见下表)

### 2.4 环境变量清单

| 变量 | 值 | 来源 |
|---|---|---|
| `APP_ENV` | `production` | 写死 |
| `LOG_LEVEL` | `INFO` | 写死 |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Railway PostgreSQL 变量,改 scheme 为 `+asyncpg` |
| `REDIS_URL` | `redis://...` | Railway Redis 变量 |
| `QDRANT_URL` | `https://xxx.aws.cloud.qdrant.io:6333` | Qdrant Cloud |
| `QDRANT_API_KEY` | `xxx` | Qdrant Cloud |
| `QDRANT_COLLECTION` | `job_agent_chunks_bge_m3_sf` | 写死 |
| `ENABLE_VECTOR_SEARCH` | `true` | 写死 |
| `LLM_BACKEND` | `openai` | 写死 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | 写死 |
| `DEEPSEEK_API_KEY` | 你的 key | DeepSeek 控制台 |
| `LLM_MODEL` | `deepseek-chat` | 写死 |
| `JUDGE_BACKEND` | `openai` | 写死(评测用) |
| `JUDGE_MODEL` | `deepseek-chat` | 写死 |
| `EMBEDDING_BACKEND` | `siliconflow` | 写死 |
| `EMBEDDING_DIM` | `1024` | 写死 |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | 写死 |
| `SILICONFLOW_API_KEY` | 你的 key | SiliconFlow |
| `SILICONFLOW_BASE_URL` | `https://api.siliconflow.cn` | 写死 |
| `RATE_LIMIT_ENABLED` | `true` | 写死 |
| `CORS_ORIGINS` | `["https://你的项目.vercel.app"]` | 部署完前端回填(见 3.3) |

### 2.5 部署 + 验证

1. Railway → **Deploy**,等 build 完成(约 2-3 分钟)
2. **Settings → Networking → Generate Domain**,得到形如 `xxx.up.railway.app` 的公网 URL
3. 验证:
   ```bash
   export BACKEND=https://xxx.up.railway.app
   curl $BACKEND/health     # {"status":"ok"}
   curl $BACKEND/ready      # database/redis/qdrant 全 ok
   ```

如果 `/ready` 任一项 false,看 Railway **Logs**。

### 2.6 灌数据(必须,否则前端无 JD 可用)

Railway 后端 service → **Settings → Command** → 改为 `sh -c "python -m app.main"` 不行,需要 Railway shell。

更简单:本地配置生产 env 后跑 ingest:

```bash
# 临时把生产 DATABASE_URL/QDRANT_URL 设到本地 .env 或 export
export DATABASE_URL='postgresql+asyncpg://...'  # 生产
export QDRANT_URL='https://...'  # 生产
export QDRANT_API_KEY='...'  # 生产
export QDRANT_COLLECTION='job_agent_chunks_bge_m3_sf'
export EMBEDDING_BACKEND=siliconflow
export EMBEDDING_DIM=1024
export EMBEDDING_MODEL=BAAI/bge-m3
export SILICONFLOW_API_KEY='...'
export SILICONFLOW_BASE_URL='https://api.siliconflow.cn'
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy

# 灌 sample JD
.venv/bin/python scripts/ingest.py --vectors

# 灌 8 条 eval JD(用户 demo 时有更多内容)
.venv/bin/python scripts/ingest_eval_jds.py
```

预期:`Ingested 3 JDs into PG` + `Ingested 8 eval JDs`。

或者用 Railway 的 **Service → Settings → Command** 临时改为:
```
sh -c "python scripts/ingest.py --vectors && python scripts/ingest_eval_jds.py"
```
跑一次后改回 Dockerfile 默认。**不推荐**,会污染生产 env。

## 3. Vercel 前端部署

### 3.1 Import

1. https://vercel.com/new
2. 选你的 GitHub repo → **Import**

### 3.2 配置

- **Framework Preset**:Next.js(自动检测)
- **Root Directory**:`frontend/`(重要!点 Expand 后选 frontend 文件夹)
- **Build Command**:`npm run build`(默认)
- **Output Directory**:`.next`(默认)

### 3.3 环境变量

| 变量 | 值 |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `https://xxx.up.railway.app`(填 2.5 的 Railway URL,无尾斜杠) |

### 3.4 部署 + 回填 CORS

1. **Deploy**,等 build 完成(约 1-2 分钟)
2. 部署完得到 Vercel URL,形如 `https://job-agent-web.vercel.app`
3. **回到 Railway**,把后端的 `CORS_ORIGINS` 改为 `["https://job-agent-web.vercel.app"]`
4. 等 Railway 自动 redeploy(约 30 秒)

## 4. 端到端冒烟

打开 `https://job-agent-web.vercel.app`:

1. **上传**:拖一个 PDF/DOCX 简历 → 看到 "Resume linked"
2. **保存 JD**:用默认 SAMPLE_JD → 点 "Save JD" → 看到 "JD saved"
3. **运行**:点 "Run" → SSE 事件流应该在 Trace 面板依次出现:`conversation` → `planner` → `retriever` → `analyzer` → `complete` → `done`
4. **历史**:左侧应该出现刚跑过的会话;点 "New chat" → 列表保留旧会话;点旧会话 → 加载历史消息
5. **超限验证**(可选):连续点 Run 30 次,第 31 次应该返回 429

任一步骤失败:
- 前端报 "Failed to fetch" → 检查 `NEXT_PUBLIC_API_BASE_URL` 和 CORS
- 后端 500 → 看 Railway Logs
- `/ready` 返回 degraded → 检查 DATABASE_URL scheme 是 `postgresql+asyncpg`

## 5. 常见踩坑

| 症状 | 原因 | 解决 |
|---|---|---|
| 前端调 API 报 CORS | `CORS_ORIGINS` 没回填 Vercel URL | Railway → Variables → 改 |
| 后端启动报 `could not connect to database` | `DATABASE_URL` scheme 没加 `+asyncpg` | 改为 `postgresql+asyncpg://...` |
| `/ready` qdrant false | API key 没填或 Cluster 没起来 | Qdrant Cloud Dashboard 检查 |
| 上传报 413 | Railway 默认 body 限制 | 暂时本地测;或 Railway 改 max request size |
| Rate limit 误伤 | 自己测试触发 | 后端 Variables 设 `RATE_LIMIT_HEAVY_PER_MIN=9999` 临时关 |

## 6. 后续(可选)

- 自定义域名:Vercel → Settings → Domains;Railway → Settings → Networking → Custom Domain
- 加 Embedding 缓存(Redis):D12 暂未做
- 加评测看板前端:D13+
