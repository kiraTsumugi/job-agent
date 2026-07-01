"""Optional Agent graph integration test.

Run with:
    RUN_AGENT_TESTS=1 pytest tests/test_agent_integration.py
"""

from __future__ import annotations

import os

import pytest

from app.agent.graph import AgentGraph
from scripts.ingest import ingest_jds


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_AGENT_TESTS") != "1",
    reason="set RUN_AGENT_TESTS=1 and start PostgreSQL/Qdrant to run Agent integration tests",
)


@pytest.mark.asyncio
async def test_agent_graph_analyze_and_rewrite_flow_with_mock_llm():
    await ingest_jds(write_vectors=True)

    graph = AgentGraph(tracer=None)
    events = [
        event
        async for event in graph.astream(
            "我的简历包含 Python 和 FastAPI 项目，请分析 AI Agent 实习 JD 的匹配度"
        )
    ]

    event_types = [event["type"] for event in events]
    assert "node:planner" in event_types
    assert "node:retriever" in event_types
    assert "node:analyzer" in event_types

    analyzer_event = next(event for event in events if event["type"] == "node:analyzer")
    analysis = analyzer_event["data"]["gap_analysis"]
    assert analysis["match_score"] > 0
    assert "gaps" in analysis

    rewrite_events = [
        event
        async for event in graph.astream(
            "请改写我的项目经历，更突出 FastAPI、LangGraph 和 RAG 经验"
        )
    ]

    event_types = [event["type"] for event in rewrite_events]
    assert "node:rewriter" in event_types

    rewriter_event = next(event for event in rewrite_events if event["type"] == "node:rewriter")
    rewritten = rewriter_event["data"]["rewritten"]
    assert rewritten["sections"]
    assert "LangGraph" in rewritten["sections"][0]["keywords_added"]
