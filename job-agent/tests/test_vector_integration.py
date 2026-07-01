"""Optional Qdrant vector integration tests.

Run with:
    RUN_VECTOR_TESTS=1 pytest tests/test_vector_integration.py
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from qdrant_client import QdrantClient

from app.core.config import settings
from app.rag.embedder import embed_query
from app.rag.ingest import ingest_jd


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_VECTOR_TESTS") != "1",
    reason="set RUN_VECTOR_TESTS=1 and start Qdrant to run vector integration tests",
)


def test_qdrant_ingest_and_query_roundtrip():
    marker = f"VectorNeedleLangGraph{uuid.uuid4().hex}"
    jd_id = f"vector_test_{uuid.uuid4().hex}"

    count = asyncio.run(
        ingest_jd(
            jd_id=jd_id,
            text=f"{marker} 需要 LangGraph、RAG、Qdrant 和 Tool Calling 经验。",
            chunking_strategy="semantic",
        )
    )
    assert count == 1

    async def query():
        return await embed_query(marker)

    vector = asyncio.run(query())
    client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None)
    result = client.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        query=vector,
        limit=5,
        with_payload=True,
    )

    owner_ids = [(point.payload or {}).get("owner_id") for point in result.points]
    assert jd_id in owner_ids
