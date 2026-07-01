"""评测执行器：遍历评测集，跑 Agent 链路，收集结果."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import EvalCase, EvalResult
from app.eval.judge import judge_output
from app.agent.graph import AgentGraph
from app.agent.prompts import build_prompt_manifest, resolve_prompt_version

logger = logging.getLogger(__name__)

EVAL_USER_MESSAGE = "请基于评测样本中的简历和 JD，分析匹配度、关键差距和优先处理项。"


async def run_evaluation(
    db: AsyncSession,
    run_id: str,
    prompt_version: str = "v1",
    chunking_strategy: str | None = None,
) -> dict:
    """跑全量评测集，返回汇总报告."""
    resolved_prompt_version = resolve_prompt_version(prompt_version)
    prompt_manifest = build_prompt_manifest(resolved_prompt_version)
    result = await db.execute(select(EvalCase))
    cases = result.scalars().all()

    scores = {"factuality": 0.0, "relevance": 0.0, "completeness": 0.0}
    total = len(cases)

    for case in cases:
        model_output = await _run_agent_for_case(case, prompt_version=resolved_prompt_version)

        # LLM-as-Judge 打分
        judge_scores = await judge_output(
            resume_text=case.resume_text,
            jd_text=case.jd_text,
            model_output=model_output,
            expected_gaps=case.expected_gaps,
            expected_rewrite_points=case.expected_rewrite_points,
        )

        # 存结果
        eval_result = EvalResult(
            id=str(uuid.uuid4()),
            case_id=case.id,
            run_id=run_id,
            model_output=model_output,
            judge_scores=judge_scores,
            prompt_version=resolved_prompt_version,
            chunking_strategy=chunking_strategy,
        )
        db.add(eval_result)

        for key in scores:
            scores[key] += judge_scores.get(key, 0)

    await db.commit()

    # 归一化均值
    if total > 0:
        for key in scores:
            scores[key] = round(scores[key] / total, 2)

    logger.info(
        "Eval run %s: total=%d prompt_version=%s prompt_fingerprint=%s scores=%s",
        run_id,
        total,
        resolved_prompt_version,
        prompt_manifest["fingerprint"][:12],
        scores,
    )
    return {
        "run_id": run_id,
        "total": total,
        "scores": scores,
        "prompt_version": resolved_prompt_version,
        "prompt_fingerprint": prompt_manifest["fingerprint"],
    }


async def _run_agent_for_case(case: EvalCase, *, prompt_version: str = "v1") -> dict:
    graph = AgentGraph(tracer=None)  # eval 不走 trace 减少噪音
    events = []
    async for event in graph.astream(
        EVAL_USER_MESSAGE,
        resume_text=case.resume_text,
        jd_text=case.jd_text,
        prompt_version=prompt_version,
    ):
        events.append(event)
    return _select_model_output(events)


def _select_model_output(events: list[dict]) -> dict:
    for event in reversed(events):
        if event.get("type") == "complete":
            return event.get("data") or {}
    return events[-1]["data"] if events else {}
