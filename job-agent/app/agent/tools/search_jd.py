"""Tool: 搜索同类 JD."""

import logging

from app.rag.retriever import hybrid_search

logger = logging.getLogger(__name__)

search_jd_tool = {
    "name": "search_jd",
    "description": "根据岗位名称或关键词，从 JD 知识库中检索最相关的岗位描述。返回 Top5 结果。",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词，如 'AI Agent 实习生 岗位要求'",
            },
            "top_k": {
                "type": "integer",
                "description": "返回结果数量",
                "default": 5,
            },
        },
        "required": ["query"],
    },
}


async def execute_search_jd(query: str, top_k: int = 5) -> list[dict]:
    results = await hybrid_search(query, top_k=top_k, use_rerank=True)
    return [{"id": r.id, "text": r.text, "score": r.score} for r in results]
