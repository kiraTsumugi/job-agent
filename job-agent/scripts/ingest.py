"""一键将 data/jds/ 入库至 PG，并可选写入 Qdrant."""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def ingest_jds(write_vectors: bool = False):
    """从 data/jds/*.json 读取 JD 并入库."""
    jd_dir = Path("data/jds")
    if not jd_dir.exists():
        logger.warning("data/jds/ 目录不存在")
        return

    from app.models.db import AsyncSessionLocal, Base, JD, async_engine

    if write_vectors:
        from app.rag.ingest import ingest_jd

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    count = 0
    vector_count = 0
    async with AsyncSessionLocal() as db:
        for jd_file in jd_dir.glob("*.json"):
            data = json.loads(jd_file.read_text(encoding="utf-8"))
            items = data if isinstance(data, list) else [data]
            for item in items:
                jd = await _upsert_jd(db, item)
                if not jd:
                    continue
                count += 1
                if write_vectors:
                    vector_count += await ingest_jd(
                        jd_id=jd.id,
                        text=jd.raw_text,
                        chunking_strategy="semantic",
                    )
        await db.commit()

    logger.info("Ingested %d JDs into PG", count)
    if write_vectors:
        logger.info("Ingested %d JD chunks into vector store", vector_count)


async def _upsert_jd(db, item: dict):
    from sqlalchemy import select

    from app.models.db import JD

    title = item.get("title") or item.get("position") or "未命名岗位"
    company = item.get("company") or "未知公司"
    raw_text = item.get("raw_text") or item.get("text") or item.get("description") or ""
    source_url = item.get("source_url") or item.get("url")
    jd_id = item.get("id")

    if not raw_text.strip():
        logger.warning("Skip JD without text: title=%s company=%s", title, company)
        return None

    existing = None
    if jd_id:
        existing = await db.get(JD, str(jd_id))
    if not existing and source_url:
        result = await db.execute(select(JD).where(JD.source_url == source_url))
        existing = result.scalar_one_or_none()

    if existing:
        existing.title = title
        existing.company = company
        existing.raw_text = raw_text
        existing.source_url = source_url
        return existing

    values = dict(
        title=title,
        company=company,
        raw_text=raw_text,
        source_url=source_url,
    )
    if jd_id:
        values["id"] = str(jd_id)

    jd = JD(**values)
    db.add(jd)
    await db.flush()
    return jd


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--vectors",
        action="store_true",
        help="also write JD chunks into Qdrant; this may load local embedding models",
    )
    args = parser.parse_args()

    await ingest_jds(write_vectors=args.vectors)
    logger.info("Ingestion complete")


if __name__ == "__main__":
    asyncio.run(main())
