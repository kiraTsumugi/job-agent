"""评测 API 端点."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import AsyncSessionLocal, EvalCase, EvalResult
from app.models.schemas import EvalCaseCreate, EvalRunRequest, EvalRunResponse, TraceSummary

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


@router.post("/eval/cases", status_code=201)
async def create_eval_case(body: EvalCaseCreate, db: AsyncSession = Depends(get_db)):
    case = EvalCase(**body.model_dump())
    db.add(case)
    await db.commit()
    return {"id": case.id}


@router.get("/eval/cases")
async def list_eval_cases(skip: int = 0, limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EvalCase).offset(skip).limit(limit).order_by(EvalCase.created_at.desc()))
    return result.scalars().all()


@router.post("/eval/run", response_model=EvalRunResponse)
async def run_eval(body: EvalRunRequest, db: AsyncSession = Depends(get_db)):
    """触发一次评测跑分."""
    from app.eval.runner import run_evaluation

    report = await run_evaluation(db, body.run_id, body.prompt_version, body.chunking_strategy)
    return EvalRunResponse(**report)


@router.get("/eval/results")
async def list_eval_results(run_id: str | None = None, db: AsyncSession = Depends(get_db)):
    q = select(EvalResult)
    if run_id:
        q = q.where(EvalResult.run_id == run_id)
    result = await db.execute(q.order_by(EvalResult.created_at.desc()).limit(200))
    return result.scalars().all()
