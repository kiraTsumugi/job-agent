"""Tool: 简历-JD 匹配打分."""

import logging

from app.services.llm import llm_complete, parse_llm_json_object

logger = logging.getLogger(__name__)

score_match_tool = {
    "name": "score_match",
    "description": "评估简历与目标 JD 的匹配度，输出 0-100 分数和逐维度评分。",
    "parameters": {
        "type": "object",
        "properties": {
            "resume_text": {"type": "string", "description": "简历全文"},
            "jd_text": {"type": "string", "description": "JD 全文"},
        },
        "required": ["resume_text", "jd_text"],
    },
}


async def execute_score_match(resume_text: str, jd_text: str) -> dict:
    prompt = f"""你是一个招聘匹配评估器。请评估以下简历与 JD 的匹配度。

JD：
{jd_text[:2000]}

简历：
{resume_text[:2000]}

输出 JSON：
{{
  "overall_score": 75,
  "dimensions": {{
    "skill_match": 80,
    "experience_match": 60,
    "education_match": 90,
    "keyword_coverage": 70
  }},
  "verdict": "推荐面试|可考虑|不建议"
}}
"""
    raw = await llm_complete(prompt=prompt, max_tokens=500)
    try:
        return parse_llm_json_object(raw)
    except ValueError:
        return {"overall_score": 0, "raw": raw}
