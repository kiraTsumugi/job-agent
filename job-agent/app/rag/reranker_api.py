"""SiliconFlow rerank API 包装. 签名与 reranker.rerank 一致, 便于切换."""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

API_PATH = "/v1/rerank"
DEFAULT_TIMEOUT = 30.0


async def rerank(query: str, documents: list[str], top_k: int = 5) -> list[tuple[int, float]]:
    """对召回文档重排序, 返回 [(原始索引, 分数), ...] 按分数降序.

    失败时抛出异常; 调用方负责降级处理.
    """
    if not documents:
        return []
    api_key = settings.SILICONFLOW_API_KEY
    if not api_key:
        raise RuntimeError("SILICONFLOW_API_KEY not configured")

    base_url = settings.SILICONFLOW_BASE_URL.rstrip("/")
    payload = {
        "model": settings.RERANKER_MODEL,
        "query": query,
        "documents": documents,
        "top_n": top_k,
        "return_documents": False,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        resp = await client.post(f"{base_url}{API_PATH}", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results") or []
    ranked = [(int(item["index"]), float(item["relevance_score"])) for item in results]
    ranked.sort(key=lambda x: x[1], reverse=True)
    logger.info("SiliconFlow rerank: query_len=%d docs=%d returned=%d", len(query), len(documents), len(ranked))
    return ranked[:top_k]
