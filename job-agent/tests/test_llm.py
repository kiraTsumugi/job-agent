"""LLM service tests."""

from __future__ import annotations

import json

import pytest

from app.agent.prompts import load_prompt
from app.rag.query_rewriter import rewrite_query
from app.core.config import settings
from app.services import llm as llm_service
from app.services.llm import judge_complete, llm_complete, parse_llm_json_object


@pytest.mark.asyncio
async def test_mock_planner_returns_json():
    prompt = load_prompt("plan").format(user_message="帮我分析简历和 JD 的匹配度")
    result = json.loads(await llm_complete(prompt))

    assert result["intent"] == "analyze"
    assert isinstance(result["keywords"], list)


@pytest.mark.asyncio
async def test_mock_analyzer_returns_schema():
    prompt = load_prompt("analyze").format(
        jd_context="岗位要求：Python、FastAPI、LangGraph、RAG、Qdrant",
        resume_text="项目使用 Python 和 FastAPI 构建服务",
        user_message="分析匹配度",
    )
    result = json.loads(await llm_complete(prompt))

    assert result["schema_version"] == "v2_analyze"
    assert "match_score" in result
    assert "gaps" in result
    assert "score_breakdown" in result
    assert "LangGraph" in result["skill_match"]
    assert result["gaps"][0]["id"].startswith("G")
    assert result["gaps"][0]["category"] == "must_have_skill"
    assert result["gaps"][0]["evidence_status"] in {"missing", "weak", "partial", "unknown"}


@pytest.mark.asyncio
async def test_mock_judge_returns_scores():
    result = json.loads(await judge_complete("judge this"))

    assert result["factuality"] == 4
    assert result["relevance"] == 4
    assert result["completeness"] == 4


@pytest.mark.asyncio
async def test_openai_judge_reuses_openai_chat_path(monkeypatch):
    calls = []

    async def fake_openai_chat_complete(**kwargs):
        calls.append(kwargs)
        return json.dumps({"factuality": 5, "relevance": 4, "completeness": 3})

    monkeypatch.setattr(settings, "JUDGE_BACKEND", "openai")
    monkeypatch.setattr(settings, "JUDGE_MODEL", "deepseek-chat")
    monkeypatch.setattr(llm_service, "_openai_chat_complete", fake_openai_chat_complete)

    result = json.loads(await judge_complete("judge this", max_tokens=321))

    assert result["factuality"] == 5
    assert calls == [
        {
            "prompt": "judge this",
            "model": "deepseek-chat",
            "max_tokens": 321,
            "temperature": 0.1,
        }
    ]


@pytest.mark.asyncio
async def test_mock_query_rewriter_keeps_current_query():
    rewritten = await rewrite_query(
        "继续分析这个岗位",
        history=[{"role": "user", "content": "我想看 FastAPI Agent 实习岗位"}],
    )

    assert rewritten == "继续分析这个岗位"


def test_parse_llm_json_object_accepts_markdown_fence():
    parsed = parse_llm_json_object('```json\n{"match_score": 80, "gaps": []}\n```')

    assert parsed == {"match_score": 80, "gaps": []}


def test_parse_llm_json_object_extracts_object_from_text():
    parsed = parse_llm_json_object('结果如下：\n{"intent": "analyze"}\n请参考。')

    assert parsed == {"intent": "analyze"}
