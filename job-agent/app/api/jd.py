"""JD 管理 CRUD 端点."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import AsyncSessionLocal, JD as JDModel
from app.models.schemas import JDCreate, JDResponse, SearchRequest, SearchHit
from app.rag.retriever import hybrid_search

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


@router.post("/jds", response_model=JDResponse, status_code=201)
async def create_jd(body: JDCreate, db: AsyncSession = Depends(get_db)):
    jd = JDModel(**body.model_dump())
    db.add(jd)
    await db.commit()
    await db.refresh(jd)
    return _jd_to_response(jd)


@router.get("/jds", response_model=list[JDResponse])
async def list_jds(skip: int = 0, limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(JDModel).offset(skip).limit(limit).order_by(JDModel.created_at.desc()))
    return [_jd_to_response(r) for r in result.scalars()]


@router.get("/jds/{jd_id}", response_model=JDResponse)
async def get_jd(jd_id: str, db: AsyncSession = Depends(get_db)):
    jd = await db.get(JDModel, jd_id)
    if not jd:
        raise HTTPException(404, "JD 不存在")
    return _jd_to_response(jd)


@router.post("/jds/search", response_model=list[SearchHit])
async def search_jds(body: SearchRequest):
    """跨 JD 库混合检索."""
    results = await hybrid_search(body.query, top_k=body.top_k, use_rerank=body.use_rerank)
    return results


def _jd_to_response(jd: JDModel) -> JDResponse:
    return JDResponse(
        id=jd.id,
        title=jd.title,
        company=jd.company,
        raw_text=jd.raw_text,
        structured=jd.structured,
        source_url=jd.source_url,
        created_at=jd.created_at,
    )
