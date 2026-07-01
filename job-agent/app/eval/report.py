"""Eval report export helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import build_prompt_manifest
from app.core.config import settings
from app.models.db import EvalCase, EvalResult

SCORE_KEYS = ("factuality", "relevance", "completeness")


async def build_eval_report(
    db: AsyncSession,
    run_id: str,
    *,
    metadata_cases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    result = await db.execute(
        select(EvalResult, EvalCase)
        .join(EvalCase, EvalResult.case_id == EvalCase.id)
        .where(EvalResult.run_id == run_id)
        .order_by(EvalResult.created_at, EvalResult.id)
    )
    rows = result.all()
    if not rows:
        raise ValueError(f"no eval results found for run_id={run_id}")
    return build_report_payload(run_id, rows, metadata_cases=metadata_cases)


def build_report_payload(
    run_id: str,
    rows: list[tuple[EvalResult, EvalCase]],
    *,
    metadata_cases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    metadata_by_key = {
        _case_key(case["resume_text"], case["jd_text"]): case
        for case in metadata_cases or []
        if "resume_text" in case and "jd_text" in case
    }
    metadata_order = {
        _case_key(case["resume_text"], case["jd_text"]): index
        for index, case in enumerate(metadata_cases or [])
        if "resume_text" in case and "jd_text" in case
    }
    rows = sorted(rows, key=lambda row: _row_order(row, metadata_order))
    cases = [
        _case_entry(index, result, case, metadata_by_key.get(_case_key(case.resume_text, case.jd_text)))
        for index, (result, case) in enumerate(rows, start=1)
    ]
    prompt_version = _common_value(cases, "prompt_version")
    return {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "llm_backend": settings.LLM_BACKEND,
            "llm_model": settings.LLM_MODEL,
            "judge_backend": settings.JUDGE_BACKEND,
            "judge_model": settings.JUDGE_MODEL,
            "prompt_version": prompt_version,
            "prompt_manifest": _prompt_manifest(prompt_version),
            "chunking_strategy": _common_value(cases, "chunking_strategy"),
        },
        "summary": {
            "total": len(cases),
            "scores": _average_scores([case["judge_scores"] for case in cases]),
        },
        "cases": cases,
    }


def write_eval_report(
    report: dict[str, Any],
    output_dir: Path,
    *,
    archive: bool = False,
) -> tuple[Path, Path]:
    output_dir = _report_archive_dir(report, output_dir) if archive else output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = _safe_filename(report["run_id"])
    json_path = output_dir / f"{run_id}.json"
    markdown_path = output_dir / f"{run_id}.md"

    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(format_markdown_report(report), encoding="utf-8")
    return json_path, markdown_path


def load_eval_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_report_diff(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    regression_threshold: float = 0.0,
) -> dict[str, Any]:
    baseline_config = _report_config(baseline)
    candidate_config = _report_config(candidate)
    baseline_cases = {_diff_case_key(case): case for case in baseline.get("cases", [])}
    candidate_cases = {_diff_case_key(case): case for case in candidate.get("cases", [])}

    matched = []
    for index, case in enumerate(candidate.get("cases", []), start=1):
        key = _diff_case_key(case)
        if key not in baseline_cases:
            continue
        matched.append(_diff_case_delta(index, baseline_cases[key], case, regression_threshold))

    regressions = sorted(
        [case for case in matched if case["is_regression"]],
        key=lambda case: (case["worst_delta"], case["index"]),
    )
    return {
        "baseline_run_id": baseline["run_id"],
        "candidate_run_id": candidate["run_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline_config": baseline_config,
        "candidate_config": candidate_config,
        "summary": {
            "baseline": baseline["summary"],
            "candidate": candidate["summary"],
            "delta": _score_delta(
                baseline.get("summary", {}).get("scores", {}),
                candidate.get("summary", {}).get("scores", {}),
            ),
            "matched_cases": len(matched),
            "regression_count": len(regressions),
            "new_case_count": len(set(candidate_cases) - set(baseline_cases)),
            "missing_case_count": len(set(baseline_cases) - set(candidate_cases)),
        },
        "regressions": regressions,
        "cases": matched,
        "new_cases": [_case_brief(candidate_cases[key]) for key in sorted(set(candidate_cases) - set(baseline_cases))],
        "missing_cases": [_case_brief(baseline_cases[key]) for key in sorted(set(baseline_cases) - set(candidate_cases))],
    }


def write_report_diff(
    diff: dict[str, Any],
    output_dir: Path,
    *,
    archive: bool = False,
) -> tuple[Path, Path]:
    output_dir = _diff_archive_dir(diff, output_dir) if archive else output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    name = f"{_safe_filename(diff['baseline_run_id'])}__vs__{_safe_filename(diff['candidate_run_id'])}"
    json_path = output_dir / f"{name}.diff.json"
    markdown_path = output_dir / f"{name}.diff.md"
    json_path.write_text(json.dumps(diff, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    markdown_path.write_text(format_markdown_diff(diff), encoding="utf-8")
    return json_path, markdown_path


def format_markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    scores = summary["scores"]
    config = report["config"]
    lines = [
        f"# Eval Report: {report['run_id']}",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Total cases: `{summary['total']}`",
        f"- LLM: `{config['llm_backend']} / {config['llm_model']}`",
        f"- Judge: `{config['judge_backend']} / {config['judge_model']}`",
        f"- Prompt version: `{config.get('prompt_version')}`",
        f"- Prompt fingerprint: `{_manifest_fingerprint(config.get('prompt_manifest'))}`",
        f"- Chunking strategy: `{config.get('chunking_strategy')}`",
        "",
        "## Summary",
        "",
        "| factuality | relevance | completeness |",
        "|---:|---:|---:|",
        (
            f"| {_fmt_score(scores.get('factuality'))} | "
            f"{_fmt_score(scores.get('relevance'))} | "
            f"{_fmt_score(scores.get('completeness'))} |"
        ),
        "",
        "## Cases",
        "",
        (
            "| # | case_type | title | decision | match_score | factuality | relevance | "
            "completeness | first_gap_category | first_gap |"
        ),
        "|---:|---|---|---|---:|---:|---:|---:|---|---|",
    ]
    for case in report["cases"]:
        scores = case["judge_scores"]
        lines.append(
            "| {index} | {case_type} | {title} | {decision} | {match_score} | {factuality} | "
            "{relevance} | {completeness} | {first_gap_category} | {first_gap} |".format(
                index=case["index"],
                case_type=_md(case.get("case_type") or ""),
                title=_md(case.get("title") or ""),
                decision=_md(case.get("decision") or ""),
                match_score=_fmt_score(case.get("match_score")),
                factuality=_fmt_score(scores.get("factuality")),
                relevance=_fmt_score(scores.get("relevance")),
                completeness=_fmt_score(scores.get("completeness")),
                first_gap_category=_md(case.get("first_gap_category") or ""),
                first_gap=_md(case.get("first_gap") or ""),
            )
        )
    lines.append("")
    return "\n".join(lines)


def format_markdown_diff(diff: dict[str, Any]) -> str:
    delta = diff["summary"]["delta"]
    baseline_scores = diff["summary"]["baseline"]["scores"]
    candidate_scores = diff["summary"]["candidate"]["scores"]
    baseline_config = diff.get("baseline_config", {})
    candidate_config = diff.get("candidate_config", {})
    lines = [
        f"# Eval Diff: {diff['baseline_run_id']} -> {diff['candidate_run_id']}",
        "",
        f"- Generated at: `{diff['generated_at']}`",
        (
            f"- Prompt versions: `{baseline_config.get('prompt_version')}` -> "
            f"`{candidate_config.get('prompt_version')}`"
        ),
        (
            f"- Prompt fingerprints: `{_manifest_fingerprint(baseline_config.get('prompt_manifest'))}` -> "
            f"`{_manifest_fingerprint(candidate_config.get('prompt_manifest'))}`"
        ),
        f"- Matched cases: `{diff['summary']['matched_cases']}`",
        f"- Regressions: `{diff['summary']['regression_count']}`",
        f"- New cases: `{diff['summary']['new_case_count']}`",
        f"- Missing cases: `{diff['summary']['missing_case_count']}`",
        "",
        "## Summary Delta",
        "",
        "| metric | baseline | candidate | delta |",
        "|---|---:|---:|---:|",
    ]
    for key in SCORE_KEYS:
        lines.append(
            f"| {key} | {_fmt_score(baseline_scores.get(key))} | "
            f"{_fmt_score(candidate_scores.get(key))} | {_fmt_delta(delta.get(key))} |"
        )

    lines.extend(["", "## Regressions", ""])
    if not diff["regressions"]:
        lines.append("No degraded cases.")
    else:
        lines.extend(
            [
                "| # | title | degraded_dimensions | factuality_delta | relevance_delta | completeness_delta | match_score_delta |",
                "|---:|---|---|---:|---:|---:|---:|",
            ]
        )
        for case in diff["regressions"]:
            score_delta = case["judge_score_delta"]
            lines.append(
                "| {index} | {title} | {dims} | {factuality} | {relevance} | {completeness} | {match_score} |".format(
                    index=case["index"],
                    title=_md(case.get("title") or ""),
                    dims=_md(", ".join(case["degraded_dimensions"])),
                    factuality=_fmt_delta(score_delta.get("factuality")),
                    relevance=_fmt_delta(score_delta.get("relevance")),
                    completeness=_fmt_delta(score_delta.get("completeness")),
                    match_score=_fmt_delta(case.get("match_score_delta")),
                )
            )

    lines.extend(["", "## All Matched Cases", ""])
    lines.extend(
        [
            "| # | title | factuality_delta | relevance_delta | completeness_delta | match_score_delta |",
            "|---:|---|---:|---:|---:|---:|",
        ]
    )
    for case in diff["cases"]:
        score_delta = case["judge_score_delta"]
        lines.append(
            "| {index} | {title} | {factuality} | {relevance} | {completeness} | {match_score} |".format(
                index=case["index"],
                title=_md(case.get("title") or ""),
                factuality=_fmt_delta(score_delta.get("factuality")),
                relevance=_fmt_delta(score_delta.get("relevance")),
                completeness=_fmt_delta(score_delta.get("completeness")),
                match_score=_fmt_delta(case.get("match_score_delta")),
            )
        )
    lines.append("")
    return "\n".join(lines)


def _case_entry(
    index: int,
    result: EvalResult,
    case: EvalCase,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    model_output = result.model_output or {}
    analysis = model_output.get("gap_analysis") if isinstance(model_output, dict) else {}
    analysis = analysis if isinstance(analysis, dict) else {}
    gaps = analysis.get("gaps") if isinstance(analysis.get("gaps"), list) else []
    first_gap = gaps[0].get("requirement") if gaps and isinstance(gaps[0], dict) else ""
    first_gap_category = gaps[0].get("category") if gaps and isinstance(gaps[0], dict) else ""
    metadata = metadata or {}

    return {
        "index": index,
        "case_uid": metadata.get("id"),
        "case_fingerprint": _case_fingerprint(case.resume_text, case.jd_text),
        "case_id": case.id,
        "result_id": result.id,
        "title": metadata.get("title") or _extract_prefixed_line(case.jd_text, "岗位："),
        "company": metadata.get("company") or _extract_prefixed_line(case.jd_text, "公司："),
        "source": metadata.get("source") or _extract_prefixed_line(case.jd_text, "来源："),
        "source_url": metadata.get("source_url"),
        "case_type": metadata.get("case_type"),
        "keyword_score": metadata.get("keyword_score"),
        "prompt_version": result.prompt_version,
        "chunking_strategy": result.chunking_strategy,
        "created_at": result.created_at.isoformat() if result.created_at else None,
        "judge_scores": _normalize_scores(result.judge_scores or {}),
        "analysis_schema_version": analysis.get("schema_version"),
        "decision": analysis.get("decision"),
        "match_score": analysis.get("match_score"),
        "gap_count": len(gaps),
        "first_gap_category": str(first_gap_category),
        "first_gap": str(first_gap),
        "expected_gaps": case.expected_gaps or [],
        "expected_rewrite_points": case.expected_rewrite_points or [],
    }


def _diff_case_delta(
    index: int,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    regression_threshold: float,
) -> dict[str, Any]:
    judge_score_delta = _score_delta(
        baseline.get("judge_scores", {}),
        candidate.get("judge_scores", {}),
    )
    degraded_dimensions = [
        key
        for key, value in judge_score_delta.items()
        if value < -regression_threshold
    ]
    match_score_delta = _numeric_delta(baseline.get("match_score"), candidate.get("match_score"))
    worst_delta = min([*judge_score_delta.values(), match_score_delta if match_score_delta is not None else 0.0])
    return {
        "index": index,
        "case_key": _diff_case_key(candidate),
        "case_id": candidate.get("case_id"),
        "title": candidate.get("title") or baseline.get("title"),
        "company": candidate.get("company") or baseline.get("company"),
        "case_type": candidate.get("case_type") or baseline.get("case_type"),
        "source_url": candidate.get("source_url") or baseline.get("source_url"),
        "baseline_judge_scores": _normalize_scores(baseline.get("judge_scores", {})),
        "candidate_judge_scores": _normalize_scores(candidate.get("judge_scores", {})),
        "judge_score_delta": judge_score_delta,
        "baseline_match_score": baseline.get("match_score"),
        "candidate_match_score": candidate.get("match_score"),
        "match_score_delta": match_score_delta,
        "degraded_dimensions": degraded_dimensions,
        "is_regression": bool(degraded_dimensions),
        "worst_delta": round(worst_delta, 2),
    }


def _score_delta(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, float]:
    return {
        key: round(float(candidate.get(key, 0)) - float(baseline.get(key, 0)), 2)
        for key in SCORE_KEYS
    }


def _numeric_delta(baseline: Any, candidate: Any) -> float | None:
    if baseline is None or candidate is None:
        return None
    return round(float(candidate) - float(baseline), 2)


def _diff_case_key(case: dict[str, Any]) -> str:
    return str(
        case.get("source_url")
        or case.get("case_uid")
        or case.get("case_fingerprint")
        or case.get("case_id")
        or f"{case.get('title')}|{case.get('company')}"
    )


def _case_brief(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_key": _diff_case_key(case),
        "case_uid": case.get("case_uid"),
        "case_fingerprint": case.get("case_fingerprint"),
        "case_id": case.get("case_id"),
        "title": case.get("title"),
        "company": case.get("company"),
        "source_url": case.get("source_url"),
    }


def _average_scores(scores_list: list[dict[str, float]]) -> dict[str, float]:
    if not scores_list:
        return {key: 0.0 for key in SCORE_KEYS}
    return {
        key: round(sum(float(scores.get(key, 0)) for scores in scores_list) / len(scores_list), 2)
        for key in SCORE_KEYS
    }


def _normalize_scores(scores: dict[str, Any]) -> dict[str, float]:
    return {key: float(scores.get(key, 0)) for key in SCORE_KEYS}


def _common_value(cases: list[dict[str, Any]], key: str) -> Any:
    values = {case.get(key) for case in cases}
    if len(values) == 1:
        return values.pop()
    return "mixed"


def _prompt_manifest(prompt_version: Any) -> dict[str, Any] | None:
    if not prompt_version or prompt_version == "mixed":
        return None
    try:
        return build_prompt_manifest(str(prompt_version))
    except FileNotFoundError as exc:
        return {"version": str(prompt_version), "error": str(exc)}


def _report_config(report: dict[str, Any]) -> dict[str, Any]:
    config = dict(report.get("config", {}))
    if config.get("prompt_version") and not config.get("prompt_manifest"):
        config["prompt_manifest"] = _prompt_manifest(config["prompt_version"])
    return config


def _manifest_fingerprint(manifest: Any) -> str:
    if not isinstance(manifest, dict):
        return ""
    fingerprint = manifest.get("fingerprint")
    if fingerprint:
        return str(fingerprint)[:12]
    return str(manifest.get("error") or "")


def _report_archive_dir(report: dict[str, Any], output_dir: Path) -> Path:
    prompt_version = report.get("config", {}).get("prompt_version") or "unknown"
    return output_dir / f"prompt_{_safe_filename(str(prompt_version))}"


def _diff_archive_dir(diff: dict[str, Any], output_dir: Path) -> Path:
    baseline_version = diff.get("baseline_config", {}).get("prompt_version") or "unknown"
    candidate_version = diff.get("candidate_config", {}).get("prompt_version") or "unknown"
    return output_dir / (
        f"prompt_{_safe_filename(str(baseline_version))}"
        f"__vs__prompt_{_safe_filename(str(candidate_version))}"
    )


def _extract_prefixed_line(text: str, prefix: str) -> str:
    for line in text.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    return ""


def _case_key(resume_text: str, jd_text: str) -> tuple[str, str]:
    return resume_text, jd_text


def _case_fingerprint(resume_text: str, jd_text: str) -> str:
    payload = json.dumps(
        {"resume_text": resume_text, "jd_text": jd_text},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _row_order(
    row: tuple[EvalResult, EvalCase],
    metadata_order: dict[tuple[str, str], int],
) -> tuple[int, str]:
    result, case = row
    key = _case_key(case.resume_text, case.jd_text)
    return metadata_order.get(key, 1_000_000), result.id


def _safe_filename(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in value)


def _fmt_score(value: Any) -> str:
    if value is None:
        return ""
    return f"{float(value):.2f}"


def _fmt_delta(value: Any) -> str:
    if value is None:
        return ""
    number = float(value)
    return f"{number:+.2f}"


def _md(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")[:180]
