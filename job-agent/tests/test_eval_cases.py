"""Eval case file tests."""

from __future__ import annotations

import json

import pytest

from scripts.eval_run import load_cases
from scripts.build_real_eval_cases import _case_from_job
from scripts.real_jd_quality_smoke import JobPost


def test_load_cases_validates_required_fields(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text(
        json.dumps(
            {
                "resume_text": "resume",
                "jd_text": "jd",
                "expected_gaps": ["gap"],
                "expected_rewrite_points": ["point"],
            }
        ),
        encoding="utf-8",
    )

    cases = load_cases(path)

    assert len(cases) == 1
    assert cases[0]["expected_gaps"] == ["gap"]


def test_load_cases_rejects_missing_required_fields(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text(json.dumps({"resume_text": "resume"}), encoding="utf-8")

    with pytest.raises(ValueError, match="missing fields"):
        load_cases(path)


def test_real_jd_case_contains_eval_metadata():
    case = _case_from_job(
        JobPost(
            source="test",
            title="Senior GenAI Engineer",
            company="Example",
            url="https://example.com/job",
            description="Build LLM Agent and RAG systems with Python.",
            score=6,
        ),
        1,
    )

    assert case["id"] == "real_jd_001"
    assert case["case_type"] == "high_relevance"
    assert case["keyword_score"] == 6
    assert case["expected_gaps"]
    assert case["expected_rewrite_points"]
