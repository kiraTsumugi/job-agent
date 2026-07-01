"""LLM-as-Judge: 用 Claude Haiku 对模型输出打分."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.llm import judge_complete, parse_llm_json_object

logger = logging.getLogger(__name__)

JUDGE_PROMPT = """你是一个严格但公正的评估器。请根据以下维度给模型输出打分，每个维度 1-5 分，严格使用以下锚点。

## 评估维度与锚点

### factuality (事实性)
- 5：完全基于简历/JD 客观事实，无编造，证据引用准确
- 3：主体事实正确，但存在 1 处模糊措辞或微小推断
- 1：存在明显编造，或大量简历中不存在的事实

### relevance (相关性)
- 5：每个 gap 都指向 JD 中真实存在的要求，方向准确
- 3：大部分 gap 相关，但有 1-2 个泛泛或与 JD 关联较弱
- 1：多数 gap 与 JD 无关或方向错误

### completeness (完整性)
- 5：覆盖全部 expected_gaps，且改写/补救建议充分
- 3：覆盖 expected_gaps 的 50%-80%，或建议不充分
- 1：漏掉 >50% expected_gaps，且无有效建议

2/4 分严格对应中间水平。

## 关键判定规则

1. 语言一致性不扣分：如果模型输出的 gap 描述使用了 JD 原文语言（中文 JD→中文，英文 JD→英文），这是正确行为，绝不应因语言选择本身扣 factuality/relevance/completeness 分。
2. expected_gaps checklist：设 N = expected_gaps 条数（无标注时 N=0，跳过此规则）。
   - 模型覆盖 ≥ ⌈N × 0.6⌉ 条 → completeness 必须 ≥ 4
   - 模型覆盖 < ⌈N × 0.3⌉ 条 → completeness 必须 ≤ 2
   覆盖判定：模型 gap 内容与某条 expected_gap 表达相同要求即视为覆盖（语义匹配，非字面匹配）。
3. 不因 gap 数量多而扣分：只看是否覆盖了 expected_gaps，多余的 gap 不影响 completeness（除非与 JD 完全无关，则计入 relevance）。

## 输入
简历：
{resume}

JD：
{jd}

模型输出：
{output}

预期 gap 参考（人工标注，N 条）：
{expected_gaps}

预期改写要点参考（人工标注）：
{expected_rewrite}

## 输出格式
严格输出 JSON：
{{
  "factuality": 4,
  "relevance": 3,
  "completeness": 4
}}

不要输出 Markdown 代码块，不要输出解释文字，只输出一个 JSON 对象（无 comment 字段）。
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
        "字段只能包含 factuality、relevance、completeness（无 comment 字段）。"
        f"\n\n上一次输出：\n{raw[:1000]}"
    )


def _preview(raw: str) -> str:
    return raw[:300].replace("\n", " ")
