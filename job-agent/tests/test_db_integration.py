"""Optional database integration tests.

Run with:
    RUN_DB_TESTS=1 pytest tests/test_db_integration.py
"""

from __future__ import annotations

import os
import uuid

import pytest

from app.main import app


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1",
    reason="set RUN_DB_TESTS=1 and start PostgreSQL to run database integration tests",
)


@pytest.mark.filterwarnings("ignore:Using `httpx` with `starlette.testclient` is deprecated")
def test_jd_search_endpoint_returns_seeded_results():
    from fastapi.testclient import TestClient

    marker = f"NeedleLangGraphFastAPI{uuid.uuid4().hex}"

    with TestClient(app) as client:
        created = client.post(
            "/api/jds",
            json={
                "title": f"AI Agent 集成测试 {marker}",
                "company": "测试公司",
                "raw_text": (
                    f"{marker} 需要 LangGraph、FastAPI、RAG、"
                    "Tool Calling 和 PostgreSQL 检索经验。"
                ),
                "source_url": f"https://example.com/integration/{marker}",
            },
        )
        assert created.status_code == 201

        response = client.post(
            "/api/jds/search",
            json={
                "query": marker,
                "top_k": 3,
                "use_rerank": False,
            },
        )

    assert response.status_code == 200
    hits = response.json()
    assert hits
    assert hits[0]["metadata"]["title"] == f"AI Agent 集成测试 {marker}"
