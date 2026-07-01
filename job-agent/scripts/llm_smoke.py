"""Smoke test the configured LLM backend without printing secrets."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Callable
from typing import Any

from app.agent.prompts import load_prompt
from app.core.config import settings
from app.rag.query_rewriter import rewrite_query
from app.services.llm import llm_complete, parse_llm_json_object


def _require_keys(*keys: str) -> Callable[[dict[str, Any]], None]:
    def validate(data: dict[str, Any]) -> None:
        missing = [key for key in keys if key not in data]
        if missing:
            raise AssertionError(f"missing keys: {missing}")

    return validate


async def _json_case(
    name: str,
    prompt: str,
    *,
    max_tokens: int,
    validate: Callable[[dict[str, Any]], None],
) -> None:
    raw = await llm_complete(prompt=prompt, max_tokens=max_tokens, temperature=0.1)
    try:
        data = parse_llm_json_object(raw)
        validate(data)
    except Exception as exc:
        preview = raw[:500].replace("\n", " ")
        print(f"{name}: FAIL ({type(exc).__name__}: {exc})")
        print(f"{name}: RAW_PREVIEW {preview}")
        raise
    print(f"{name}: OK keys={','.join(data.keys())}")


async def _query_rewrite_case() -> None:
    rewritten = await rewrite_query(
        "继续分析这个岗位",
        history=[{"role": "user", "content": "我想看 FastAPI Agent 实习岗位"}],
    )
    if not rewritten.strip():
        raise AssertionError("query rewrite returned empty text")
    if rewritten.strip().startswith("{"):
        raise AssertionError(f"query rewrite returned JSON-looking text: {rewritten[:120]}")
    print(f"query_rewrite: OK text={rewritten[:80]}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default=None, help="override LLM_BACKEND, e.g. openai")
    args = parser.parse_args()

    if args.backend:
        settings.LLM_BACKEND = args.backend

    print(f"backend: {settings.LLM_BACKEND}")
    print(f"model: {settings.LLM_MODEL}")
    print(f"base_url: {settings.DEEPSEEK_BASE_URL}")

    await _json_case(
        "planner",
        load_prompt("plan").format(user_message="帮我分析简历和 AI Agent 实习 JD 的匹配度"),
        max_tokens=500,
        validate=_require_keys("intent", "target_sections", "keywords", "notes"),
    )
    await _json_case(
        "analyzer",
        load_prompt("analyze").format(
            jd_context="岗位要求：Python、FastAPI、LangGraph、RAG、Qdrant",
            resume_text="项目使用 Python 和 FastAPI 构建后端服务，了解 RAG。",
            user_message="分析匹配度",
        ),
        max_tokens=2400,
        validate=_require_keys("schema_version", "match_score", "skill_match", "gaps", "strengths", "summary"),
    )
    await _json_case(
        "rewriter",
        load_prompt("rewrite").format(
            user_message="请改写我的项目经历，突出 FastAPI、LangGraph、RAG",
            gap_analysis=json.dumps(
                {"gaps": [{"requirement": "LangGraph", "suggestion": "补充 Agent 编排经验"}]},
                ensure_ascii=False,
            ),
        ),
        max_tokens=1800,
        validate=_require_keys("sections", "diff_summary"),
    )
    await _query_rewrite_case()


if __name__ == "__main__":
    asyncio.run(main())
