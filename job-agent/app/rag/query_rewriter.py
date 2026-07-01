"""查询改写：用于多轮对话中扩展/澄清用户意图，提升 RAG 召回率."""

from __future__ import annotations

import logging

from app.services.llm import llm_complete

logger = logging.getLogger(__name__)

REWRITE_PROMPT = """你是一个查询改写助手。根据对话历史和当前用户输入，生成一个更适合向量检索的独立查询。
只输出改写后的查询，不要加任何解释。

对话历史：
{history}

当前用户输入：{query}

改写查询："""


async def rewrite_query(query: str, history: list[dict] | None = None) -> str:
    """基于对话历史改写查询，用于多轮对话场景."""
    if not history:
        return query

    # 只取最近 3 轮
    recent = history[-6:]
    history_text = "\n".join(
        f"{'用户' if m['role'] == 'user' else '助手'}: {m['content']}" for m in recent
    )

    try:
        rewritten = await llm_complete(
            prompt=REWRITE_PROMPT.format(history=history_text, query=query),
            max_tokens=200,
        )
        logger.debug("Rewrote query: '%s' -> '%s'", query, rewritten)
        return rewritten.strip() or query
    except Exception:
        logger.exception("Query rewrite failed, using original")
        return query


async def generate_hypothetical_answer(query: str) -> str:
    """HyDE: 让 LLM 先生成假想答案，再用假想答案检索."""
    prompt = f"请根据以下问题写一段可能的回答，不需要保证完全正确，只用于后续检索：\n\n{query}\n\n回答："
    try:
        return await llm_complete(prompt=prompt, max_tokens=300)
    except Exception:
        return query
