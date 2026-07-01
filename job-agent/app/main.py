from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import AsyncQdrantClient
from redis.asyncio import from_url as redis_from_url
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import setup_logging
from app.api import chat, upload, jd, eval as eval_api
from app.models.db import async_engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await async_engine.dispose()


app = FastAPI(
    title="AI 求职助手",
    description="简历 × JD 智能匹配与改写 Agent API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(jd.router, prefix="/api", tags=["jd"])
app.include_router(eval_api.router, prefix="/api", tags=["eval"])


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    checks = {
        "database": await _check_database(),
        "redis": await _check_redis(),
        "qdrant": await _check_qdrant(),
    }
    return {
        "status": "ok" if all(item["ok"] for item in checks.values()) else "degraded",
        "checks": checks,
    }


async def _check_database() -> dict:
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("select 1"))
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": exc.__class__.__name__}


async def _check_redis() -> dict:
    client = redis_from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
    try:
        await client.ping()
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": exc.__class__.__name__}
    finally:
        await client.aclose()


async def _check_qdrant() -> dict:
    if not settings.ENABLE_VECTOR_SEARCH:
        return {"ok": True, "skipped": True}
    client = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY or None,
    )
    try:
        await client.get_collections()
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": exc.__class__.__name__}
    finally:
        await client.close()
