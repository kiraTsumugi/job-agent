"""Tool: 抽取简历技能."""

import logging

from app.services.llm import llm_complete, parse_llm_json_object

logger = logging.getLogger(__name__)

extract_skills_tool = {
    "name": "extract_skills",
    "description": "从简历文本中提取硬技能、软技能、工具栈，返回结构化 JSON。",
    "parameters": {
        "type": "object",
        "properties": {
            "resume_text": {
                "type": "string",
                "description": "简历全文",
            },
        },
        "required": ["resume_text"],
    },
}


async def execute_extract_skills(resume_text: str) -> dict:
    prompt = f"""从以下简历中提取技能，输出 JSON：
{{
  "languages": ["Python", "Go"],
  "frameworks": ["FastAPI", "LangGraph"],
  "tools": ["Docker", "Qdrant"],
  "soft_skills": ["团队协作"],
  "years_of_experience": 2
}}

简历：
{resume_text[:3000]}
"""
    raw = await llm_complete(prompt=prompt, max_tokens=500)
    try:
        return parse_llm_json_object(raw)
    except ValueError:
        return {"raw": raw}
