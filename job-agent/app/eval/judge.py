"""LLM-as-Judge: 用 Claude Haiku 对模型输出打分."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.llm import judge_complete, parse_llm_json_object

logger = logging.getLogger(__name__)

JUDGE_PROMPT = """你是一个严格但公正的评估器。请根据以下维度给模型输出打分，每个维度 1-5 分（5 为最佳）。

## 评估维度
- factuality (事实性)：输出是否基于简历和 JD 的客观事实，有无编造
- relevance (相关性)：是否准确回应了用户的意图和 JD 要求
- completeness (完整性)：是否覆盖了所有关键 gap，改写建议是否充分

## 输入
简历：
{resume}

JD：
{jd}

模型输出：
{output}

预期 gap 参考（人工标注）：
{expected_gaps}

预期改写要点参考（人工标注）：
{expected_rewrite}

## 输出格式
严格输出 JSON：
{{
  "factuality": 4,
  "relevance": 3,
  "completeness": 4,
  "comment": "简要说明扣分原因"
}}

不要输出 Markdown 代码块，不要输出解释文字，只输出一个 JSON 对象。
"""


async def judge_output(
    resume_text: str,
    jd_text: str,
    model_output: dict[str, Any],
    expected_gaps: list[str] | None = None,
    expected_rewrite_points: list[str] | None = None,
) -> dict[str, float]:
    """返回 {factuality, relevance, completeness} 打分."""
    prompt = JUDGE_PROMPT.format(
        resume=resume_text[:2000],
        jd=jd_text[:2000],
        output=json.dumps(model_output, ensure_ascii=False, indent=2),
        expected_gaps=json.dumps(expected_gaps or [], ensure_ascii=False),
        expected_rewrite=json.dumps(expected_rewrite_points or [], ensure_ascii=False),
    )

    raw = await judge_complete(prompt=prompt, max_tokens=500)
    try:
        return _parse_judge_scores(raw)
    except ValueError as e:
        logger.warning("Judge parse failed: %s raw=%s", e, _preview(raw))

    retry_raw = await judge_complete(prompt=_retry_prompt(prompt, raw), max_tokens=500)
    try:
        return _parse_judge_scores(retry_raw)
    except ValueError as e:
        logger.warning("Judge retry parse failed: %s raw=%s", e, _preview(retry_raw))
        return {"factuality": 0, "relevance": 0, "completeness": 0}


def _parse_judge_scores(raw: str) -> dict[str, float]:
    scores = parse_llm_json_object(raw)
    logger.debug("Judge scores: %s", scores)
    return {
        "factuality": _score(scores, "factuality"),
        "relevance": _score(scores, "relevance"),
        "completeness": _score(scores, "completeness"),
    }


def _score(scores: dict[str, Any], key: str) -> float:
    value = float(scores[key])
    if not 1 <= value <= 5:
        raise ValueError(f"{key} out of range: {value}")
    return value


def _retry_prompt(prompt: str, raw: str) -> str:
    return (
        f"{prompt}\n\n"
        "上一次输出无法被 JSON 解析。请重新输出，必须只返回一个 JSON 对象，"
        "字段只能包含 factuality、relevance、completeness、comment。"
        f"\n\n上一次输出：\n{raw[:1000]}"
    )


def _preview(raw: str) -> str:
    return raw[:300].replace("\n", " ")
