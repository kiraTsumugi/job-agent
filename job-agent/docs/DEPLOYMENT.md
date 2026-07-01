# Deployment Notes

## Backend

Target: Railway or Fly.io.

Required services:

- PostgreSQL
- Redis
- Qdrant or Qdrant Cloud

Required environment:

```bash
APP_ENV=production
LOG_LEVEL=INFO
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...
QDRANT_URL=https://...
QDRANT_API_KEY=
QDRANT_COLLECTION=job_agent_chunks_bge_m3_sf
ENABLE_VECTOR_SEARCH=true
LLM_BACKEND=openai
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_API_KEY=...
LLM_MODEL=deepseek-chat
EMBEDDING_BACKEND=siliconflow
EMBEDDING_DIM=1024
EMBEDDING_MODEL=BAAI/bge-m3
SILICONFLOW_API_KEY=...
SILICONFLOW_BASE_URL=https://api.siliconflow.cn
CORS_ORIGINS=["https://your-frontend.vercel.app"]
```

Health checks:

- `GET /health`: liveness, no dependency checks
- `GET /ready`: PostgreSQL, Redis, Qdrant diagnostics

Docker uses `${PORT:-8000}`, so Railway/Fly injected ports work without editing the image.

## Frontend

Target: Vercel.

Project root:

```text
frontend
```

Required environment:

```bash
NEXT_PUBLIC_API_BASE_URL=https://your-backend.example.com
```

Local run:

```bash
cd frontend
npm install
npm run dev
```

## Smoke Test

After deployment:

```bash
curl https://your-backend.example.com/health
curl https://your-backend.example.com/ready
```

Then open the Vercel URL, upload a resume, save a JD, and run one analyze request.
