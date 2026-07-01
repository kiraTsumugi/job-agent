"""检索节点：从 Qdrant 中检索最相关的 JD chunks."""

from __future__ import annotations

import logging

from app.agent.state import AgentState
from app.rag.retriever import hybrid_search
from app.rag.query_rewriter import rewrite_query

logger = logging.getLogger(__name__)


async def retriever_node(state: AgentState) -> dict:
    """根据用户意图检索相关 JD."""
    query = state["user_message"]

    # 如果有对话历史，先做查询改写
    rewritten = await rewrite_query(query, history=state.get("conversation_history"))
    if rewritten != query:
        logger.debug("Query rewritten: %s -> %s", query, rewritten)
        query = rewritten

    results = await hybrid_search(query, top_k=5, use_rerank=True)

    return {"retrieved_jds": [{"id": r.id, "text": r.text, "score": r.score} for r in results] if results else []}
