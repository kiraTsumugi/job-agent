"""Hybrid Search: BM25 + 向量 + RRF 融合."""

from __future__ import annotations

import logging
import math
import re
import asyncio
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.models.db import AsyncSessionLocal, JD
from app.core.config import settings
from app.models.schemas import SearchHit
from app.rag.embedder import embed_query

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9_+#.-]*|[\u4e00-\u9fff]+", re.IGNORECASE)


@dataclass(frozen=True)
class _Document:
    id: str
    text: str
    metadata: dict
    tokens: list[str]


async def hybrid_search(query: str, top_k: int = 5, use_rerank: bool = True) -> list[SearchHit]:
    """
    混合检索流程:
    1. BM25 关键词召回 (top_k * 2)
    2. 向量语义召回 (top_k * 2)
    3. RRF 融合排序
    4. 可选 bge-reranker 重排
    """
    logger.info("Hybrid search: query=%s top_k=%d use_rerank=%s", query, top_k, use_rerank)
    query_tokens = _tokenize(query)
    if not query.strip() or not query_tokens:
        return []

    docs = await _load_jd_documents()
    if not docs:
        logger.info("Hybrid search skipped: no JDs in database")
        return []

    bm25_ranked = _bm25_rank(query_tokens, docs)
    phrase_ranked = _phrase_rank(query, docs)
    vector_ranked = await _vector_rank(query, limit=max(top_k * 4, top_k))
    fused = _reciprocal_rank_fusion_many([bm25_ranked, phrase_ranked, vector_ranked])

    doc_by_id = {doc.id: doc for doc in docs}
    candidates = [
        (doc_by_id[doc_id], score)
        for doc_id, score in fused
        if doc_id in doc_by_id
    ][: max(top_k * 4, top_k)]

    if use_rerank and settings.ENABLE_LOCAL_RERANKER and candidates:
        candidates = await _rerank_candidates(query, candidates, top_k)

    hits = [
        SearchHit(
            id=doc.id,
            text=doc.text,
            score=round(float(score), 6),
            metadata=doc.metadata,
        )
        for doc, score in candidates[:top_k]
    ]
    logger.info("Hybrid search returned %d hits", len(hits))
    return hits


async def _load_jd_documents() -> list[_Document]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(JD).order_by(JD.created_at.desc()))
        rows = result.scalars().all()

    docs = []
    for row in rows:
        text = _format_jd_text(row)
        tokens = _tokenize(text)
        if not tokens:
            continue
        docs.append(
            _Document(
                id=row.id,
                text=text,
                metadata={
                    "title": row.title,
                    "company": row.company,
                    "source_url": row.source_url,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "retrieval": "bm25+phrase+vector-rrf",
                },
                tokens=tokens,
            )
        )
    return docs


def _format_jd_text(jd: JD) -> str:
    return "\n".join(
        part for part in [f"{jd.title} @ {jd.company}", jd.raw_text] if part
    )


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for match in _WORD_RE.findall(text.lower()):
        if _is_cjk(match):
            tokens.extend(match)
            tokens.extend(match[i : i + 2] for i in range(len(match) - 1))
        else:
            tokens.append(match)
    return tokens


def _is_cjk(text: str) -> bool:
    return all("\u4e00" <= ch <= "\u9fff" for ch in text)


def _bm25_rank(query_tokens: list[str], docs: list[_Document]) -> list[tuple[str, float]]:
    if not docs:
        return []

    doc_freq: Counter[str] = Counter()
    term_freqs: list[Counter[str]] = []
    doc_lengths: list[int] = []

    for doc in docs:
        tf = Counter(doc.tokens)
        term_freqs.append(tf)
        doc_lengths.append(len(doc.tokens))
        doc_freq.update(tf.keys())

    avgdl = sum(doc_lengths) / len(doc_lengths)
    unique_query_tokens = set(query_tokens)
    k1 = 1.5
    b = 0.75
    ranked: list[tuple[str, float]] = []

    for doc, tf, dl in zip(docs, term_freqs, doc_lengths):
        score = 0.0
        for token in unique_query_tokens:
            freq = tf.get(token, 0)
            if not freq:
                continue
            df = doc_freq[token]
            idf = math.log(1 + (len(docs) - df + 0.5) / (df + 0.5))
            denom = freq + k1 * (1 - b + b * dl / avgdl)
            score += idf * (freq * (k1 + 1) / denom)
        if score > 0:
            ranked.append((doc.id, score))

    return sorted(ranked, key=lambda item: item[1], reverse=True)


def _phrase_rank(query: str, docs: list[_Document]) -> list[tuple[str, float]]:
    normalized_query = query.strip().lower()
    if not normalized_query:
        return []

    ranked: list[tuple[str, float]] = []
    for doc in docs:
        normalized_doc = doc.text.lower()
        score = 0.0
        if normalized_query in normalized_doc:
            score += 2.0
        for part in re.split(r"\s+", normalized_query):
            if len(part) >= 2 and part in normalized_doc:
                score += 1.0
        if score > 0:
            ranked.append((doc.id, score))
    return sorted(ranked, key=lambda item: item[1], reverse=True)


async def _vector_rank(query: str, limit: int) -> list[tuple[str, float]]:
    if not settings.ENABLE_VECTOR_SEARCH:
        return []

    try:
        vector = await embed_query(query)
        return await asyncio.to_thread(_query_qdrant, vector, limit)
    except Exception:
        logger.exception("Vector search failed, falling back to lexical search")
        return []


def _query_qdrant(vector: list[float], limit: int) -> list[tuple[str, float]]:
    client = QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY or None,
    )
    if not client.collection_exists(settings.QDRANT_COLLECTION):
        return []

    result = client.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        query=vector,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="doc_type",
                    match=MatchValue(value="jd"),
                )
            ]
        ),
        limit=limit,
        with_payload=True,
    )
    ranked = []
    for point in result.points:
        owner_id = (point.payload or {}).get("owner_id")
        if owner_id:
            ranked.append((owner_id, float(point.score)))
    return ranked


async def _rerank_candidates(
    query: str,
    candidates: list[tuple[_Document, float]],
    top_k: int,
) -> list[tuple[_Document, float]]:
    try:
        from app.rag.reranker import rerank

        order = await rerank(query, [doc.text for doc, _ in candidates], top_k=top_k)
        return [(candidates[idx][0], score) for idx, score in order]
    except Exception:
        logger.exception("Local reranker failed, falling back to BM25/RRF order")
        return candidates


# ─── RRF 融合 ──────────────────────────────────────────

def reciprocal_rank_fusion(
    results_a: list[tuple[str, float]],
    results_b: list[tuple[str, float]],
    k: int = 60,
) -> list[tuple[str, float]]:
    """将两个排序列表按 RRF 公式融合."""
    return _reciprocal_rank_fusion_many([results_a, results_b], k=k)


def _reciprocal_rank_fusion_many(
    result_sets: list[list[tuple[str, float]]],
    k: int = 60,
) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for results in result_sets:
        for rank, (doc_id, _) in enumerate(results):
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
