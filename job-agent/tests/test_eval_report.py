"""Eval report tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

from app.eval.report import (
    build_report_diff,
    build_report_payload,
    format_markdown_diff,
    format_markdown_report,
    write_eval_report,
    write_report_diff,
)


def _result(case_id: str, scores: dict, match_score: int):
    return SimpleNamespace(
        id=f"result-{case_id}",
        case_id=case_id,
        run_id="run-a",
        model_output={"gap_analysis": {"match_score": match_score, "gaps": [{"requirement": "gap"}]}},
        judge_scores=scores,
        prompt_version="v1",
        chunking_strategy=None,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _v2_result(case_id: str, scores: dict, match_score: int):
    return SimpleNamespace(
        id=f"result-{case_id}",
        case_id=case_id,
        run_id="run-a",
        model_output={
            "gap_analysis": {
                "schema_version": "v2_analyze",
                "decision": "possible_match",
                "match_score": match_score,
                "gaps": [
                    {
                        "id": "G1",
                        "category": "must_have_skill",
                        "requirement": "LangGraph production experience",
                    }
                ],
            }
        },
        judge_scores=scores,
        prompt_version="v2",
        chunking_strategy=None,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _case(case_id: str, title: str):
    jd_text = f"岗位：{title}\n公司：Example\n来源：test\n\nJD body"
    return SimpleNamespace(
        id=case_id,
        resume_text="resume",
        jd_text=jd_text,
        expected_gaps=["gap"],
        expected_rewrite_points=["point"],
    )


def test_build_report_payload_computes_summary_and_cases():
    rows = [
        (_result("case-1", {"factuality": 5, "relevance": 3, "completeness": 4}, 70), _case("case-1", "AI Engineer")),
        (_result("case-2", {"factuality": 3, "relevance": 5, "completeness": 2}, 40), _case("case-2", "SRE")),
    ]
    metadata_cases = [
        {
            "resume_text": "resume",
            "jd_text": rows[0][1].jd_text,
            "id": "fixture-001",
            "title": "AI Engineer",
            "company": "Example",
            "source": "fixture",
            "case_type": "high_relevance",
            "keyword_score": 8,
        }
    ]

    report = build_report_payload("run-a", rows, metadata_cases=metadata_cases)

    assert report["summary"]["total"] == 2
    assert report["summary"]["scores"] == {
        "factuality": 4.0,
        "relevance": 4.0,
        "completeness": 3.0,
    }
    assert report["config"]["prompt_version"] == "v1"
    assert len(report["config"]["prompt_manifest"]["fingerprint"]) == 64
    assert report["cases"][0]["case_type"] == "high_relevance"
    assert report["cases"][0]["case_uid"] == "fixture-001"
    assert len(report["cases"][0]["case_fingerprint"]) == 64
    assert report["cases"][0]["match_score"] == 70
    assert report["cases"][1]["title"] == "SRE"


def test_build_report_payload_keeps_v2_analyzer_fields():
    report = build_report_payload(
        "run-v2",
        [(_v2_result("case-1", {"factuality": 5, "relevance": 4, "completeness": 4}, 72), _case("case-1", "AI Engineer"))],
    )

    case = report["cases"][0]
    assert report["config"]["prompt_version"] == "v2"
    assert report["config"]["prompt_manifest"]["files"]["analyze"] == "v2_analyze.md"
    assert case["analysis_schema_version"] == "v2_analyze"
    assert case["decision"] == "possible_match"
    assert case["first_gap_category"] == "must_have_skill"


def test_write_eval_report_writes_json_and_markdown(tmp_path):
    report = build_report_payload(
        "run/a",
        [(_result("case-1", {"factuality": 5, "relevance": 4, "completeness": 3}, 80), _case("case-1", "AI | Engineer"))],
    )

    json_path, markdown_path = write_eval_report(report, tmp_path)

    assert json_path.name == "run_a.json"
    assert markdown_path.name == "run_a.md"
    assert json.loads(json_path.read_text(encoding="utf-8"))["run_id"] == "run/a"
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Eval Report: run/a" in markdown
    assert "AI \\| Engineer" in markdown
    assert "Prompt fingerprint" in markdown


def test_write_eval_report_can_archive_by_prompt_version(tmp_path):
    report = build_report_payload(
        "run/a",
        [(_result("case-1", {"factuality": 5, "relevance": 4, "completeness": 3}, 80), _case("case-1", "AI Engineer"))],
    )

    json_path, markdown_path = write_eval_report(report, tmp_path, archive=True)

    assert json_path.parent == tmp_path / "prompt_v1"
    assert markdown_path.parent == tmp_path / "prompt_v1"
    assert json_path.name == "run_a.json"


def test_format_markdown_report_contains_summary_table():
    report = build_report_payload(
        "run-a",
        [(_result("case-1", {"factuality": 5, "relevance": 4, "completeness": 3}, 80), _case("case-1", "AI Engineer"))],
    )

    markdown = format_markdown_report(report)

    assert "| factuality | relevance | completeness |" in markdown
    assert "| 5.00 | 4.00 | 3.00 |" in markdown


def test_build_report_payload_uses_metadata_case_order():
    case_a = _case("case-a", "A")
    case_b = _case("case-b", "B")
    report = build_report_payload(
        "run-a",
        [
            (_result("case-a", {"factuality": 5, "relevance": 4, "completeness": 3}, 80), case_a),
            (_result("case-b", {"factuality": 3, "relevance": 4, "completeness": 5}, 60), case_b),
        ],
        metadata_cases=[
            {"resume_text": "resume", "jd_text": case_b.jd_text},
            {"resume_text": "resume", "jd_text": case_a.jd_text},
        ],
    )

    assert [case["title"] for case in report["cases"]] == ["B", "A"]


def test_build_report_diff_computes_score_delta_and_regressions():
    baseline = build_report_payload(
        "baseline",
        [
            (_result("case-1", {"factuality": 5, "relevance": 5, "completeness": 4}, 80), _case("case-1", "AI Engineer")),
            (_result("case-2", {"factuality": 3, "relevance": 3, "completeness": 3}, 40), _case("case-2", "SRE")),
        ],
    )
    candidate = build_report_payload(
        "candidate",
        [
            (_result("case-1", {"factuality": 5, "relevance": 4, "completeness": 4}, 82), _case("case-1", "AI Engineer")),
            (_result("case-2", {"factuality": 4, "relevance": 4, "completeness": 4}, 45), _case("case-2", "SRE")),
        ],
    )

    diff = build_report_diff(baseline, candidate)

    assert diff["summary"]["delta"] == {
        "factuality": 0.5,
        "relevance": 0.0,
        "completeness": 0.5,
    }
    assert diff["summary"]["regression_count"] == 1
    assert diff["regressions"][0]["title"] == "AI Engineer"
    assert diff["regressions"][0]["degraded_dimensions"] == ["relevance"]


def test_build_report_diff_matches_report_cases_by_stable_case_uid():
    case_a = _case("db-a", "AI Engineer")
    case_b = _case("db-b", "AI Engineer")
    metadata_a = [{"resume_text": "resume", "jd_text": case_a.jd_text, "id": "stable-case-1"}]
    metadata_b = [{"resume_text": "resume", "jd_text": case_b.jd_text, "id": "stable-case-1"}]
    baseline = build_report_payload(
        "baseline",
        [(_result("db-a", {"factuality": 5, "relevance": 5, "completeness": 5}, 80), case_a)],
        metadata_cases=metadata_a,
    )
    candidate = build_report_payload(
        "candidate",
        [(_result("db-b", {"factuality": 5, "relevance": 4, "completeness": 5}, 80), case_b)],
        metadata_cases=metadata_b,
    )

    diff = build_report_diff(baseline, candidate)

    assert diff["summary"]["matched_cases"] == 1
    assert diff["summary"]["new_case_count"] == 0
    assert diff["summary"]["missing_case_count"] == 0
    assert diff["regressions"][0]["case_key"] == "stable-case-1"


def test_write_report_diff_writes_json_and_markdown(tmp_path):
    baseline = build_report_payload(
        "base/run",
        [(_result("case-1", {"factuality": 5, "relevance": 4, "completeness": 3}, 80), _case("case-1", "AI Engineer"))],
    )
    candidate = build_report_payload(
        "candidate",
        [(_result("case-1", {"factuality": 4, "relevance": 4, "completeness": 3}, 70), _case("case-1", "AI Engineer"))],
    )
    baseline["config"].pop("prompt_manifest")
    candidate["config"].pop("prompt_manifest")
    diff = build_report_diff(baseline, candidate)

    json_path, markdown_path = write_report_diff(diff, tmp_path)

    assert json_path.name == "base_run__vs__candidate.diff.json"
    assert markdown_path.name == "base_run__vs__candidate.diff.md"
    assert diff["baseline_config"]["prompt_version"] == "v1"
    assert diff["candidate_config"]["prompt_version"] == "v1"
    assert len(diff["baseline_config"]["prompt_manifest"]["fingerprint"]) == 64
    assert len(diff["candidate_config"]["prompt_manifest"]["fingerprint"]) == 64
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Eval Diff: base/run -> candidate" in markdown
    assert "Prompt versions" in markdown
    assert "AI Engineer" in markdown


def test_write_report_diff_can_archive_by_prompt_versions(tmp_path):
    baseline = build_report_payload(
        "base/run",
        [(_result("case-1", {"factuality": 5, "relevance": 4, "completeness": 3}, 80), _case("case-1", "AI Engineer"))],
    )
    candidate = build_report_payload(
        "candidate",
        [(_result("case-1", {"factuality": 4, "relevance": 4, "completeness": 3}, 70), _case("case-1", "AI Engineer"))],
    )

    json_path, markdown_path = write_report_diff(build_report_diff(baseline, candidate), tmp_path, archive=True)

    assert json_path.parent == tmp_path / "prompt_v1__vs__prompt_v1"
    assert markdown_path.parent == tmp_path / "prompt_v1__vs__prompt_v1"


def test_format_markdown_diff_reports_no_regressions():
    baseline = build_report_payload(
        "baseline",
        [(_result("case-1", {"factuality": 3, "relevance": 3, "completeness": 3}, 70), _case("case-1", "AI Engineer"))],
    )
    candidate = build_report_payload(
        "candidate",
        [(_result("case-1", {"factuality": 4, "relevance": 4, "completeness": 4}, 75), _case("case-1", "AI Engineer"))],
    )

    markdown = format_markdown_diff(build_report_diff(baseline, candidate))

    assert "No degraded cases." in markdown
    assert "| factuality | 3.00 | 4.00 | +1.00 |" in markdown
