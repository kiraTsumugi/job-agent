from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
