"""Tool: 改写简历某段."""

import logging

from app.services.llm import llm_complete, parse_llm_json_object

logger = logging.getLogger(__name__)

rewrite_section_tool = {
    "name": "rewrite_section",
    "description": "根据用户指令和 JD 要求，改写简历中指定的段落。支持指定改写的风格和侧重点。",
    "parameters": {
        "type": "object",
        "properties": {
            "section_text": {"type": "string", "description": "要改写的原始段落"},
            "instruction": {"type": "string", "description": "改写指令，如 '更突出 RAG 经验'"},
            "jd_context": {"type": "string", "description": "目标 JD 的关键要求"},
            "style": {
                "type": "string",
                "description": "改写风格：concise|detailed|star (STAR 法则)",
                "default": "star",
            },
        },
        "required": ["section_text", "instruction"],
    },
}


async def execute_rewrite_section(
    section_text: str, instruction: str, jd_context: str = "", style: str = "star"
) -> dict:
    style_guide = {
        "concise": "简洁有力，每点一行",
        "detailed": "详细描述技术细节和量化成果",
        "star": "使用 STAR 法则（情境-任务-行动-结果）",
    }
    prompt = f"""请按以下要求改写简历段落。

改写风格：{style_guide.get(style, style_guide['star'])}
改写指令：{instruction}
JD 上下文：{jd_context or '无'}

原始段落：
{section_text}

输出 JSON：
{{
  "rewritten": "改写后的文本",
  "changes": ["改动说明1", "改动说明2"],
  "keywords_before": [],
  "keywords_after": ["新增关键词"]
}}
"""
    raw = await llm_complete(prompt=prompt, max_tokens=2000)
    try:
        return parse_llm_json_object(raw)
    except ValueError:
        return {"rewritten": raw, "changes": []}
