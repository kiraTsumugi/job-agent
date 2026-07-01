"""LLM routing with a deterministic local mock backend."""

from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

_openai_client: AsyncOpenAI | None = None
_anthropic_client: AsyncAnthropic | None = None


def parse_llm_json_object(raw: str) -> dict[str, Any]:
    """Parse a JSON object from an LLM response, allowing common markdown fences."""
    text = _strip_markdown_fence(raw.strip())
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            data, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data

    raise json.JSONDecodeError("No JSON object found in LLM response", raw, 0)


def _strip_markdown_fence(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
    return "\n".join(lines).strip()


def _get_openai() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
        )
    return _openai_client


def _get_anthropic() -> AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _anthropic_client


async def llm_complete(prompt: str, max_tokens: int = 1000, temperature: float = 0.3) -> str:
    """Main LLM call."""
    if settings.LLM_BACKEND == "mock":
        return _mock_complete(prompt)
    if settings.LLM_BACKEND != "openai":
        raise ValueError(f"Unknown LLM_BACKEND: {settings.LLM_BACKEND}")

    return await _openai_chat_complete(
        prompt=prompt,
        model=settings.LLM_MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
    )


async def judge_complete(prompt: str, max_tokens: int = 500) -> str:
    """Judge model call."""
    if settings.JUDGE_BACKEND == "mock":
        return json.dumps(
            {
                "factuality": 4,
                "relevance": 4,
                "completeness": 4,
                "comment": "mock judge",
            },
            ensure_ascii=False,
        )
    if settings.JUDGE_BACKEND == "openai":
        return await _openai_chat_complete(
            prompt=prompt,
            model=settings.JUDGE_MODEL,
            max_tokens=max_tokens,
            temperature=0.1,
        )
    if settings.JUDGE_BACKEND != "anthropic":
        raise ValueError(f"Unknown JUDGE_BACKEND: {settings.JUDGE_BACKEND}")

    client = _get_anthropic()
    resp = await client.messages.create(
        model=settings.JUDGE_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    content = resp.content[0].text if resp.content else ""
    return content.strip()


async def _openai_chat_complete(
    *,
    prompt: str,
    model: str,
    max_tokens: int,
    temperature: float,
) -> str:
    client = _get_openai()
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    content = resp.choices[0].message.content or ""
    return content.strip()


def _mock_complete(prompt: str) -> str:
    if "任务规划助手" in prompt:
        return json.dumps(_mock_plan(prompt), ensure_ascii=False)
    if "查询改写助手" in prompt:
        return _mock_query_rewrite(prompt)
    if "资深招聘顾问和简历分析师" in prompt:
        return json.dumps(_mock_analysis(prompt), ensure_ascii=False)
    if "专业简历写手" in prompt:
        return json.dumps(_mock_rewrite(prompt), ensure_ascii=False)
    return json.dumps({"message": "mock response"}, ensure_ascii=False)


def _mock_plan(prompt: str) -> dict:
    user_message = _extract_after(prompt, "用户输入：").lower()
    intent = "analyze"
    if any(word in user_message for word in ("改写", "优化", "rewrite")):
        intent = "rewrite"
    elif any(word in user_message for word in ("搜索", "岗位要求", "常见要求")):
        intent = "search"

    result = {
        "intent": intent,
        "target_sections": ["项目经历"] if intent == "rewrite" else [],
        "keywords": _extract_keywords(user_message),
        "notes": "mock backend",
    }
    if '"schema_version": "v2_plan"' in prompt:
        result["schema_version"] = "v2_plan"
    return result


def _mock_query_rewrite(prompt: str) -> str:
    current = _extract_between(prompt, "当前用户输入：", "改写查询：")
    return current.strip() or _extract_after(prompt, "当前用户输入：").strip()


def _mock_analysis(prompt: str) -> dict:
    resume = _extract_between(prompt, "## 简历全文", "## 用户输入")
    jd_context = _extract_between(prompt, "## 参考 JD 上下文", "## 简历全文")
    jd_keywords = _extract_keywords(jd_context)
    resume_keywords = set(_extract_keywords(resume))

    skill_match = {
        keyword: 90 if keyword in resume_keywords else 35
        for keyword in jd_keywords
    }
    gaps = [
        {
            "category": "技能",
            "requirement": keyword,
            "current": "简历中未明确体现" if keyword not in resume_keywords else "简历中已体现",
            "severity": "medium" if keyword not in resume_keywords else "low",
            "suggestion": f"补充与 {keyword} 相关的项目动作、指标或工具调用细节。",
        }
        for keyword in jd_keywords
        if keyword not in resume_keywords
    ]

    if not jd_keywords:
        jd_keywords = ["Python", "FastAPI", "RAG"]
        skill_match = {"Python": 70, "FastAPI": 60, "RAG": 60}

    match_score = 85 if not gaps else max(45, 85 - len(gaps) * 10)
    if '"schema_version": "v2_analyze"' in prompt:
        return _mock_analysis_v2(jd_keywords, resume_keywords, skill_match, gaps, match_score)

    return {
        "match_score": match_score,
        "skill_match": skill_match,
        "gaps": gaps[:5],
        "strengths": [f"已覆盖 {keyword}" for keyword in jd_keywords if keyword in resume_keywords][:5],
        "rewrite_priority": [str(i) for i in range(min(len(gaps), 3))],
        "summary": "mock 分析：已根据 JD 关键词和简历文本给出可测试的结构化匹配结果。",
    }


def _mock_analysis_v2(
    jd_keywords: list[str],
    resume_keywords: set[str],
    skill_match: dict[str, int],
    gaps: list[dict],
    match_score: int,
) -> dict:
    gap_entries = [
        {
            "id": f"G{index}",
            "category": "must_have_skill",
            "requirement": gap["requirement"],
            "requirement_type": "must_have",
            "resume_evidence": "" if gap["requirement"] not in resume_keywords else gap["requirement"],
            "evidence_status": "missing" if gap["requirement"] not in resume_keywords else "weak",
            "severity": "medium",
            "impact": f"JD 明确要求 {gap['requirement']}，简历证据不足会降低初筛匹配度。",
            "rewrite_action": "add_tooling",
            "suggestion": gap["suggestion"],
            "confidence": 0.8,
        }
        for index, gap in enumerate(gaps[:8], start=1)
    ]
    strengths = [
        {
            "id": f"S{index}",
            "category": "must_have_skill",
            "requirement": keyword,
            "resume_evidence": keyword,
            "relevance": "high",
        }
        for index, keyword in enumerate((keyword for keyword in jd_keywords if keyword in resume_keywords), start=1)
    ][:6]
    return {
        "schema_version": "v2_analyze",
        "match_score": match_score,
        "decision": _mock_decision(match_score),
        "score_breakdown": {
            "must_have": match_score,
            "preferred": max(0, match_score - 5),
            "evidence_quality": 80 if strengths else 45,
            "seniority_scope": 60,
            "risk": max(0, min(100, match_score - len(gap_entries) * 5)),
        },
        "skill_match": skill_match,
        "gaps": gap_entries,
        "strengths": strengths,
        "rewrite_priority": [gap["id"] for gap in gap_entries[:3]],
        "risks": [
            {
                "id": "R1",
                "risk": "关键 JD 技能缺少简历证据，可能在筛选或面试中被追问。",
                "mitigation": "只补充真实项目中做过的工具、规模、指标和职责范围。",
            }
        ] if gap_entries else [],
        "summary": "mock v2 分析：按固定 gap 分类、证据状态和优先级输出结构化匹配结果。",
    }


def _mock_decision(match_score: int) -> str:
    if match_score >= 85:
        return "strong_match"
    if match_score >= 65:
        return "possible_match"
    if match_score >= 40:
        return "weak_match"
    return "not_recommended"


def _mock_rewrite(prompt: str) -> dict:
    if '"schema_version": "v2_rewrite"' in prompt:
        return {
            "schema_version": "v2_rewrite",
            "sections": [
                {
                    "section_name": "项目经历",
                    "original": "用户提供的原始项目经历",
                    "rewritten": "基于 FastAPI、LangGraph 和 RAG 构建 Agent 主链路，接入检索、分析和改写节点，并补充可复现测试。",
                    "changes": ["突出 Agent/RAG 技术栈", "补充工程验证闭环"],
                    "keywords_added": ["FastAPI", "LangGraph", "RAG"],
                    "evidence_limits": ["缺少线上流量、成本下降或转化率等量化指标时不要编造"],
                }
            ],
            "diff_summary": "mock v2 改写：强化了技术关键词、证据边界和可验证工程产出。",
        }
    return {
        "sections": [
            {
                "section_name": "项目经历",
                "original": "用户提供的原始项目经历",
                "rewritten": "基于 FastAPI、LangGraph 和 RAG 构建 Agent 主链路，接入检索、分析和改写节点，并补充可复现测试。",
                "changes": ["突出 Agent/RAG 技术栈", "补充工程验证闭环"],
                "keywords_added": ["FastAPI", "LangGraph", "RAG"],
            }
        ],
        "diff_summary": "mock 改写：强化了技术关键词和可验证工程产出。",
    }


def _extract_keywords(text: str) -> list[str]:
    known = [
        "Python",
        "FastAPI",
        "LangGraph",
        "LangChain",
        "RAG",
        "Qdrant",
        "Milvus",
        "BM25",
        "Rerank",
        "MCP",
        "Tool Calling",
        "Prompt Engineering",
        "LLM-as-Judge",
        "PostgreSQL",
    ]
    lowered = text.lower()
    return [keyword for keyword in known if keyword.lower() in lowered]


def _extract_between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    if start == -1:
        return ""
    start += len(start_marker)
    end = text.find(end_marker, start)
    return text[start:end if end != -1 else None].strip()


def _extract_after(text: str, marker: str) -> str:
    index = text.rfind(marker)
    if index == -1:
        return ""
    return text[index + len(marker):].strip()
