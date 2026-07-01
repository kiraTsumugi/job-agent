"""Load eval cases and optionally import them into PostgreSQL."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_EVAL_PATH = Path("data/eval/real_jd_cases.jsonl")
DEFAULT_REPORT_DIR = Path("data/eval/reports")
DEFAULT_DIFF_DIR = Path("data/eval/reports/diffs")
REQUIRED_FIELDS = {"resume_text", "jd_text", "expected_gaps", "expected_rewrite_points"}


def load_cases(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"eval case file not found: {path}")

    cases: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        case = json.loads(line)
        missing = REQUIRED_FIELDS - set(case)
        if missing:
            raise ValueError(f"{path}:{line_number} missing fields: {sorted(missing)}")
        cases.append(case)
    return cases


async def import_cases(path: Path) -> int:
    from app.models.db import AsyncSessionLocal, Base, EvalCase, async_engine

    cases = load_cases(path)

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    count = 0
    async with AsyncSessionLocal() as db:
        for case in cases:
            existing = await db.execute(
                select(EvalCase.id).where(
                    EvalCase.resume_text == case["resume_text"],
                    EvalCase.jd_text == case["jd_text"],
                )
            )
            if existing.scalar_one_or_none():
                continue
            db.add(
                EvalCase(
                    resume_text=case["resume_text"],
                    jd_text=case["jd_text"],
                    expected_gaps=case.get("expected_gaps") or [],
                    expected_rewrite_points=case.get("expected_rewrite_points") or [],
                )
            )
            count += 1
        await db.commit()
    return count


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, default=DEFAULT_EVAL_PATH)
    parser.add_argument("--import-db", action="store_true", help="write cases into eval_cases table")
    parser.add_argument("--run-id", default=None, help="run evaluation over eval_cases table")
    parser.add_argument(
        "--rejudge-from",
        default=None,
        metavar="SOURCE_RUN_ID",
        help="re-score an existing run's model_output with current judge prompt; "
             "writes results under --run-id as the new run id",
    )
    parser.add_argument("--prompt-version", default="latest", help="core prompt version for --run-id")
    parser.add_argument("--export-report", action="store_true", help="export report for --run-id after running")
    parser.add_argument("--export-run-id", default=None, help="export report for an existing run_id")
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--compare-run-ids", nargs=2, metavar=("BASELINE", "CANDIDATE"))
    parser.add_argument("--compare-reports", nargs=2, type=Path, metavar=("BASELINE_JSON", "CANDIDATE_JSON"))
    parser.add_argument("--diff-dir", type=Path, default=DEFAULT_DIFF_DIR)
    parser.add_argument(
        "--archive",
        action="store_true",
        help="write reports under prompt_<version>/ and diffs under prompt_<base>__vs__prompt_<candidate>/",
    )
    args = parser.parse_args()

    cases = load_cases(args.file)
    logger.info("Loaded %d eval cases from %s", len(cases), args.file)
    for index, case in enumerate(cases, start=1):
        title = case.get("title") or "untitled"
        company = case.get("company") or "unknown"
        logger.info("Case %d/%d: %s @ %s", index, len(cases), title, company)

    if args.import_db:
        count = await import_cases(args.file)
        logger.info("Imported %d eval cases into PostgreSQL", count)

    if args.run_id:
        from app.agent.prompts import build_prompt_manifest, resolve_prompt_version
        from app.eval.runner import run_evaluation
        from app.models.db import AsyncSessionLocal

        prompt_version = resolve_prompt_version(args.prompt_version)
        prompt_manifest = build_prompt_manifest(prompt_version)
        logger.info(
            "Using prompt version %s fingerprint=%s",
            prompt_version,
            prompt_manifest["fingerprint"][:12],
        )
        async with AsyncSessionLocal() as db:
            if args.rejudge_from:
                from app.eval.runner import rejudge_run
                report = await rejudge_run(db, args.rejudge_from, args.run_id)
            else:
                report = await run_evaluation(db, args.run_id, prompt_version, None)
        logger.info("Eval report: %s", report)

    report_run_id = args.export_run_id or (args.run_id if args.export_report else None)
    if report_run_id:
        from app.eval.report import build_eval_report, write_eval_report
        from app.models.db import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            report = await build_eval_report(db, report_run_id, metadata_cases=cases)
        json_path, markdown_path = write_eval_report(report, args.report_dir, archive=args.archive)
        logger.info("Wrote eval report JSON: %s", json_path)
        logger.info("Wrote eval report Markdown: %s", markdown_path)

    if args.compare_run_ids:
        from app.eval.report import build_eval_report, build_report_diff, write_report_diff
        from app.models.db import AsyncSessionLocal

        baseline_run_id, candidate_run_id = args.compare_run_ids
        async with AsyncSessionLocal() as db:
            baseline = await build_eval_report(db, baseline_run_id, metadata_cases=cases)
            candidate = await build_eval_report(db, candidate_run_id, metadata_cases=cases)
        diff = build_report_diff(baseline, candidate)
        json_path, markdown_path = write_report_diff(diff, args.diff_dir, archive=args.archive)
        logger.info("Wrote eval diff JSON: %s", json_path)
        logger.info("Wrote eval diff Markdown: %s", markdown_path)

    if args.compare_reports:
        from app.eval.report import build_report_diff, load_eval_report, write_report_diff

        baseline_path, candidate_path = args.compare_reports
        diff = build_report_diff(load_eval_report(baseline_path), load_eval_report(candidate_path))
        json_path, markdown_path = write_report_diff(diff, args.diff_dir, archive=args.archive)
        logger.info("Wrote eval diff JSON: %s", json_path)
        logger.info("Wrote eval diff Markdown: %s", markdown_path)


if __name__ == "__main__":
    asyncio.run(main())
