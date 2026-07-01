"""Optional chat SSE integration tests.

Run with:
    RUN_CHAT_TESTS=1 pytest tests/test_chat_integration.py
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import Iterable

import pytest

from app.core.config import settings
from app.main import app
from app.models.db import AsyncSessionLocal, Conversation, async_engine
from scripts.ingest import ingest_jds


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_CHAT_TESTS") != "1",
    reason="set RUN_CHAT_TESTS=1 and start PostgreSQL/Qdrant to run chat SSE integration tests",
)


def _parse_sse(lines: Iterable[str]) -> list[dict]:
    events: list[dict] = []
    current: dict[str, list[str] | str] = {"event": "message", "data": []}

    def flush() -> None:
        data_lines = current.get("data", [])
        if not data_lines:
            return
        event = str(current.get("event") or "message")
        data = "\n".join(data_lines if isinstance(data_lines, list) else [str(data_lines)])
        events.append({"event": event, "data": json.loads(data)})

    for raw_line in lines:
        line = raw_line.rstrip("\r")
        if not line:
            flush()
            current = {"event": "message", "data": []}
            continue
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        value = value[1:] if value.startswith(" ") else value
        if field == "event":
            current["event"] = value
        elif field == "data":
            data = current.setdefault("data", [])
            assert isinstance(data, list)
            data.append(value)

    flush()
    return events


def _post_stream(client, message: str, *, conversation_id: str) -> list[dict]:
    with client.stream(
        "POST",
        "/api/chat/stream",
        json={"conversation_id": conversation_id, "message": message},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        return _parse_sse(response.iter_lines())


async def _seed_jds() -> None:
    await ingest_jds(write_vectors=True)
    await async_engine.dispose()


async def _load_messages(conversation_id: str) -> list[dict]:
    async with AsyncSessionLocal() as db:
        conversation = await db.get(Conversation, conversation_id)
        assert conversation is not None
        return conversation.messages


@pytest.mark.filterwarnings("ignore:Using `httpx` with `starlette.testclient` is deprecated")
def test_chat_stream_analyze_and_rewrite_paths(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setattr(settings, "LLM_BACKEND", "mock")
    monkeypatch.setattr(settings, "EMBEDDING_BACKEND", "hash")
    monkeypatch.setattr(settings, "ENABLE_LOCAL_RERANKER", False)

    asyncio.run(_seed_jds())
    conversation_id = f"chat-integration-{uuid.uuid4().hex}"

    with TestClient(app) as client:
        analyze_events = _post_stream(
            client,
            "我的简历包含 Python 和 FastAPI 项目，请分析 AI Agent 实习 JD 的匹配度",
            conversation_id=conversation_id,
        )
        rewrite_events = _post_stream(
            client,
            "请改写我的项目经历，更突出 FastAPI、LangGraph 和 RAG 经验",
            conversation_id=conversation_id,
        )
        detail_response = client.get(f"/api/conversations/{conversation_id}")
        list_response = client.get("/api/conversations", params={"limit": 10})

    analyze_types = [event["event"] for event in analyze_events]
    assert analyze_events[0] == {
        "event": "conversation",
        "data": {"conversation_id": conversation_id},
    }
    assert "node:planner" in analyze_types
    assert "node:retriever" in analyze_types
    assert "node:analyzer" in analyze_types
    assert "complete" in analyze_types
    assert analyze_types[-1] == "done"

    analyzer_event = next(event for event in analyze_events if event["event"] == "node:analyzer")
    analysis = analyzer_event["data"]["gap_analysis"]
    assert analysis["match_score"] > 0
    assert "gaps" in analysis

    rewrite_types = [event["event"] for event in rewrite_events]
    assert rewrite_events[0] == {
        "event": "conversation",
        "data": {"conversation_id": conversation_id},
    }
    assert "node:planner" in rewrite_types
    assert "node:retriever" in rewrite_types
    assert "node:analyzer" in rewrite_types
    assert "node:rewriter" in rewrite_types
    assert "complete" in rewrite_types
    assert rewrite_types[-1] == "done"

    rewriter_event = next(event for event in rewrite_events if event["event"] == "node:rewriter")
    rewritten = rewriter_event["data"]["rewritten"]
    assert rewritten["sections"]
    assert "LangGraph" in rewritten["sections"][0]["keywords_added"]

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == conversation_id
    assert len(detail["messages"]) == 4

    assert list_response.status_code == 200
    summaries = list_response.json()
    assert any(
        summary["id"] == conversation_id and summary["message_count"] == 4
        for summary in summaries
    )

    messages = asyncio.run(_load_messages(conversation_id))
    roles = [message["role"] for message in messages]
    assert roles == ["user", "assistant", "user", "assistant"]
    assert messages[0]["content"].startswith("我的简历包含 Python")
    assert messages[1]["metadata"]["event"] == "complete"
    assert messages[2]["content"].startswith("请改写我的项目经历")
    assert "rewritten" in json.loads(messages[3]["content"])
