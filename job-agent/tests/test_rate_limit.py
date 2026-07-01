"""Rate limit middleware tests."""

from __future__ import annotations

import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _build_app(limit: int) -> FastAPI:
    from app.core import config
    importlib.reload(config)
    config.settings.RATE_LIMIT_ENABLED = True
    config.settings.RATE_LIMIT_HEAVY_PER_MIN = limit
    config.settings.RATE_LIMIT_GENERAL_PER_MIN = limit

    from app.core import rate_limit
    importlib.reload(rate_limit)
    limiter = rate_limit.SlidingWindowLimiter(limit, 60)

    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/chat/stream")
    async def chat_stream():
        return {"ok": True}

    @app.middleware("http")
    async def rl(request, call_next):
        from app.core.rate_limit import client_ip
        if request.url.path == "/health":
            return await call_next(request)
        allowed, retry = limiter.check(client_ip(request))
        if not allowed:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=429, content={"detail": "rate limited"}, headers={"Retry-After": str(retry)})
        return await call_next(request)

    return app


def test_health_is_exempt():
    app = _build_app(limit=1)
    with TestClient(app) as client:
        for _ in range(5):
            r = client.get("/health")
            assert r.status_code == 200


def test_heavy_endpoint_returns_429_after_limit():
    app = _build_app(limit=2)
    with TestClient(app) as client:
        assert client.get("/api/chat/stream").status_code == 200
        assert client.get("/api/chat/stream").status_code == 200
        r = client.get("/api/chat/stream")
        assert r.status_code == 429
        assert "Retry-After" in r.headers


def test_429_response_shape():
    app = _build_app(limit=1)
    with TestClient(app) as client:
        client.get("/api/chat/stream")
        r = client.get("/api/chat/stream")
        assert r.status_code == 429
        body = r.json()
        assert body["detail"] == "rate limited"
        assert int(r.headers["Retry-After"]) >= 1
