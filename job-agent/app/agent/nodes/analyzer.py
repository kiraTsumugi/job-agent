"""简历-JD gap 分析节点."""

import logging

from sqlalchemy import select

from app.agent.state import AgentState
from app.services.llm import llm_complete, parse_llm_json_object
from app.agent.prompts import load_prompt
from app.models.db import AsyncSessionLocal, JD, Resume

logger = logging.getLogger(__name__)


async def analyzer_node(state: AgentState) -> dict:
    """分析简历与 JD 的差距，输出结构化 gap 列表."""
    prompt_template = load_prompt("analyze", state.get("prompt_version"))
    resume_text, jd_text = await _load_context(state)
    retrieved_context = "\n\n".join(
        f"[JD {i+1}] {r.get('text', '')}" for i, r in enumerate(state.get("retrieved_jds", []))
    )
    jd_context = jd_text or retrieved_context or "（无检索结果，请根据用户输入中的 JD 信息分析）"

    prompt = prompt_template.format(
        user_message=state["user_message"],
        resume_text=resume_text or "（无已上传简历，请根据用户输入中的简历信息分析）",
        jd_context=jd_context,
    )

    raw = await llm_complete(prompt=prompt, max_tokens=3000)

    try:
        analysis = parse_llm_json_object(raw)
        return {"gap_analysis": analysis}
    except ValueError:
        logger.warning("Analyzer JSON parse failed")
        return {"gap_analysis": {"gaps": [], "match_score": 0, "raw": raw}}


async def _load_context(state: AgentState) -> tuple[str | None, str | None]:
    """Load resume/JD text referenced by tokens without making graph state depend on DB models."""
    resume_text = state.get("resume_text")
    jd_text = state.get("jd_text")

    if resume_text and jd_text:
        return resume_text, jd_text

    async with AsyncSessionLocal() as session:
        if not resume_text and state.get("resume_token"):
            result = await session.execute(
                select(Resume.raw_text).where(Resume.upload_token == state["resume_token"])
            )
            resume_text = result.scalar_one_or_none()

        if not jd_text and state.get("jd_id"):
            result = await session.execute(select(JD.raw_text).where(JD.id == state["jd_id"]))
            jd_text = result.scalar_one_or_none()

    return resume_text, jd_text
