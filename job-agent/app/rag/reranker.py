"""bge-reranker-v2-m3 重排序."""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_reranker = None  # lazy init


def _get_reranker():
    global _reranker
    if _reranker is None:
        from FlagEmbedding import FlagReranker
        _reranker = FlagReranker(settings.RERANKER_MODEL, use_fp16=True)
    return _reranker


async def rerank(query: str, documents: list[str], top_k: int = 5) -> list[tuple[int, float]]:
    """对召回文档重排序，返回 [(原始索引, 分数), ...] 按分数降序."""
    import asyncio
    model = _get_reranker()
    pairs = [[query, doc] for doc in documents]
    scores = await asyncio.to_thread(
        lambda: model.compute_score(pairs, normalize=True)
    )
    if not isinstance(scores, list):
        scores = [scores]
    indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    return indexed[:top_k]
