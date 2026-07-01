"""任务拆解节点：识别用户意图 → 决定走哪条分支."""

import logging

from app.agent.state import AgentState
from app.services.llm import llm_complete, parse_llm_json_object
from app.agent.prompts import load_prompt

logger = logging.getLogger(__name__)


async def planner_node(state: AgentState) -> dict:
    """分析用户意图，返回执行计划."""
    prompt_template = load_prompt("plan", state.get("prompt_version"))
    prompt = prompt_template.format(user_message=state["user_message"])

    raw = await llm_complete(prompt=prompt, max_tokens=300)

    try:
        plan = parse_llm_json_object(raw)
        intent = plan.get("intent", "analyze")
        logger.info("Planned intent: %s", intent)
        return {"plan": plan}
    except ValueError:
        logger.warning("Planner JSON parse failed, defaulting to analyze")
        return {"plan": {"intent": "analyze", "target_sections": [], "notes": raw}}
