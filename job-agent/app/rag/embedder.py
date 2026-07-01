"""Embedding backends."""

from __future__ import annotations

import hashlib
import logging
import math
import re
import asyncio

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_embedder = None  # lazy init
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_+#.-]*|[\u4e00-\u9fff]+", re.IGNORECASE)
_SILICONFLOW_EMBEDDINGS_PATH = "/v1/embeddings"
_SILICONFLOW_TIMEOUT = 30.0
_SILICONFLOW_MAX_RETRIES = 3


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _embedder


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts with the configured backend."""
    if settings.EMBEDDING_BACKEND == "hash":
        return [_hash_embedding(text, settings.EMBEDDING_DIM) for text in texts]
    if settings.EMBEDDING_BACKEND == "siliconflow":
        return await _siliconflow_embed_texts(texts)
    if settings.EMBEDDING_BACKEND != "local":
        raise ValueError(f"Unknown EMBEDDING_BACKEND: {settings.EMBEDDING_BACKEND}")

    model = _get_embedder()
    import asyncio
    embeddings = await asyncio.to_thread(
        lambda: model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    )
    return embeddings.tolist()


async def embed_query(query: str) -> list[float]:
    """单条查询嵌入."""
    results = await embed_texts([query])
    return results[0]


async def _siliconflow_embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if not settings.SILICONFLOW_API_KEY:
        raise RuntimeError("SILICONFLOW_API_KEY not configured")

    base_url = settings.SILICONFLOW_BASE_URL.rstrip("/")
    payload = {
        "model": settings.EMBEDDING_MODEL,
        "input": texts,
        "encoding_format": "float",
    }
    headers = {
        "Authorization": f"Bearer {settings.SILICONFLOW_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=_SILICONFLOW_TIMEOUT) as client:
        data = await _post_siliconflow_embeddings(client, base_url, payload, headers)

    rows = sorted(data.get("data") or [], key=lambda row: int(row.get("index", 0)))
    embeddings = [row.get("embedding") for row in rows]
    if len(embeddings) != len(texts) or any(not isinstance(item, list) for item in embeddings):
        raise RuntimeError("SiliconFlow embedding response has invalid shape")
    return embeddings


async def _post_siliconflow_embeddings(
    client: httpx.AsyncClient,
    base_url: str,
    payload: dict,
    headers: dict,
) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, _SILICONFLOW_MAX_RETRIES + 1):
        try:
            resp = await client.post(f"{base_url}{_SILICONFLOW_EMBEDDINGS_PATH}", json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            last_error = exc
            if attempt == _SILICONFLOW_MAX_RETRIES:
                break
            await asyncio.sleep(0.5 * attempt)
    raise RuntimeError("SiliconFlow embedding request failed after retries") from last_error


def _hash_embedding(text: str, dim: int) -> list[float]:
    """Deterministic lightweight embedding for local tests and infrastructure checks."""
    if dim <= 0:
        raise ValueError("Embedding dimension must be positive")

    vector = [0.0] * dim
    tokens = _tokenize(text)
    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[bucket] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for match in _TOKEN_RE.findall(text.lower()):
        if all("\u4e00" <= ch <= "\u9fff" for ch in match):
            tokens.extend(match)
            tokens.extend(match[i : i + 2] for i in range(len(match) - 1))
        else:
            tokens.append(match)
    return tokens
