"""把 data/eval/real_jd_cases.jsonl 里的 JD 入库到 PG JD 表 + Qdrant.

供 retrieval A/B 评测用. jd_id 采用 `eval_{case_id}` 命名, 保证可重复执行.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_PATH = Path("data/eval/real_jd_cases.jsonl")


async def ingest_eval_jds(path: Path) -> int:
    from sqlalchemy import select
    from app.models.db import AsyncSessionLocal, Base, JD, async_engine
    from app.rag.ingest import ingest_jd

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    count = 0
    async with AsyncSessionLocal() as db:
        for case in cases:
            case_id = case.get("id") or case.get("case_id")
            if not case_id:
                logger.warning("Skip case without id: %s", case.get("title"))
                continue
            jd_id = f"eval_{case_id}"
            jd_text = case["jd_text"]
            title = (case.get("title") or "eval_jd")[:200]
            company = case.get("company") or "eval_case"

            existing = await db.get(JD, jd_id)
            if existing:
                existing.title = title
                existing.company = company
                existing.raw_text = jd_text
                existing.source_url = case.get("source_url") or f"eval://{case_id}"
            else:
                db.add(JD(
                    id=jd_id,
                    title=title,
                    company=company,
                    raw_text=jd_text,
                    source_url=case.get("source_url") or f"eval://{case_id}",
                ))
                await db.flush()
            await ingest_jd(jd_id=jd_id, text=jd_text, chunking_strategy="semantic")
            count += 1
        await db.commit()

    logger.info("Ingested %d eval JDs (jd_id=eval_<case_id>)", count)
    return count


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    await ingest_eval_jds(args.file)


if __name__ == "__main__":
    asyncio.run(main())
