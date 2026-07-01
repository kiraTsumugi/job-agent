from __future__ import annotations

import pytest

from app import main


@pytest.mark.asyncio
async def test_health_is_liveness_only():
    assert await main.health() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ready_reports_component_checks(monkeypatch):
    async def ok():
        return {"ok": True}

    async def down():
        return {"ok": False, "error": "ConnectError"}

    monkeypatch.setattr(main, "_check_database", ok)
    monkeypatch.setattr(main, "_check_redis", ok)
    monkeypatch.setattr(main, "_check_qdrant", down)

    result = await main.ready()

    assert result["status"] == "degraded"
    assert result["checks"]["database"] == {"ok": True}
    assert result["checks"]["redis"] == {"ok": True}
    assert result["checks"]["qdrant"] == {"ok": False, "error": "ConnectError"}
