"""改写节点：根据 gap 分析结果改写简历段落."""

import json
import logging

from app.agent.state import AgentState
from app.services.llm import llm_complete, parse_llm_json_object
from app.agent.prompts import load_prompt

logger = logging.getLogger(__name__)


async def rewriter_node(state: AgentState) -> dict:
    """根据 gap 分析和用户指令改写简历段."""
    prompt_template = load_prompt("rewrite", state.get("prompt_version"))
    gap_analysis = json.dumps(state.get("gap_analysis", {}), ensure_ascii=False, indent=2)

    prompt = prompt_template.format(
        user_message=state["user_message"],
        gap_analysis=gap_analysis,
    )

    raw = await llm_complete(prompt=prompt, max_tokens=3000)

    try:
        result = parse_llm_json_object(raw)
        return {"rewritten": result}
    except ValueError:
        return {"rewritten": {"sections": [], "raw": raw}}
