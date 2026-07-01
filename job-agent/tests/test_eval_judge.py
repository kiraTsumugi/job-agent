"""Judge tests."""

from __future__ import annotations

import pytest

from app.eval import judge


@pytest.mark.asyncio
async def test_judge_output_retries_when_first_response_is_not_json(monkeypatch):
    responses = iter(
        [
            "我认为这个输出整体不错，但不是 JSON。",
            '{"factuality": 4, "relevance": 3, "completeness": 5, "comment": "retry ok"}',
        ]
    )
    prompts = []

    async def fake_judge_complete(prompt: str, max_tokens: int = 500) -> str:
        prompts.append(prompt)
        return next(responses)

    monkeypatch.setattr(judge, "judge_complete", fake_judge_complete)

    scores = await judge.judge_output(
        resume_text="resume",
        jd_text="jd",
        model_output={"gap_analysis": {"match_score": 70}},
    )

    assert scores == {"factuality": 4.0, "relevance": 3.0, "completeness": 5.0}
    assert len(prompts) == 2
    assert "上一次输出无法被 JSON 解析" in prompts[1]


def test_parse_judge_scores_rejects_out_of_range_values():
    with pytest.raises(ValueError, match="out of range"):
        judge._parse_judge_scores('{"factuality": 6, "relevance": 3, "completeness": 4}')
