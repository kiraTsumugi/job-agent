"""文档入库 pipeline: 解析 → 分块 → 嵌入 → 写入 Qdrant."""

from __future__ import annotations

import logging
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.core.config import settings
from app.rag.chunker import get_chunker
from app.rag.embedder import embed_texts

logger = logging.getLogger(__name__)


async def ingest_jd(
    jd_id: str,
    text: str,
    chunking_strategy: str = "semantic",
    qdrant_client=None,
) -> int:
    """
    将一条 JD 分块后写入 Qdrant。
    返回写入的 chunk 数。
    """
    chunker = get_chunker(chunking_strategy)
    chunks = chunker.chunk(text)

    if not chunks:
        logger.warning("No chunks produced for JD %s", jd_id)
        return 0

    texts = [c["text"] for c in chunks]
    embeddings = await embed_texts(texts)
    client = qdrant_client or _get_qdrant_client()
    _ensure_collection(client, len(embeddings[0]))
    _upsert_chunks(
        client=client,
        owner_id=jd_id,
        doc_type="jd",
        chunks=chunks,
        embeddings=embeddings,
    )

    logger.info("Ingest JD %s: %d chunks, strategy=%s", jd_id, len(chunks), chunking_strategy)
    return len(chunks)


async def ingest_resume(
    resume_token: str,
    text: str,
    chunking_strategy: str = "fixed",
    qdrant_client=None,
) -> int:
    """将简历分块后写入 Qdrant."""
    chunker = get_chunker(chunking_strategy)
    chunks = chunker.chunk(text)

    if not chunks:
        return 0

    texts = [c["text"] for c in chunks]
    embeddings = await embed_texts(texts)
    client = qdrant_client or _get_qdrant_client()
    _ensure_collection(client, len(embeddings[0]))
    _upsert_chunks(
        client=client,
        owner_id=resume_token,
        doc_type="resume",
        chunks=chunks,
        embeddings=embeddings,
    )

    logger.info("Ingest resume %s: %d chunks, strategy=%s", resume_token, len(chunks), chunking_strategy)
    return len(chunks)


def _get_qdrant_client() -> QdrantClient:
    return QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY or None,
    )


def _ensure_collection(client: QdrantClient, vector_size: int) -> None:
    if client.collection_exists(settings.QDRANT_COLLECTION):
        return
    client.create_collection(
        collection_name=settings.QDRANT_COLLECTION,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def _upsert_chunks(
    client: QdrantClient,
    owner_id: str,
    doc_type: str,
    chunks: list[dict],
    embeddings: list[list[float]],
) -> None:
    points = []
    for chunk, embedding in zip(chunks, embeddings):
        chunk_id = chunk["id"]
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_type}:{owner_id}:{chunk_id}"))
        points.append(
            PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "owner_id": owner_id,
                    "doc_type": doc_type,
                    "chunk_id": chunk_id,
                    "text": chunk["text"],
                    "meta": chunk.get("meta", {}),
                },
            )
        )

    client.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)
