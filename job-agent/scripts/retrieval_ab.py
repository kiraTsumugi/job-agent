"""Retrieval A/B: 对比 hybrid_search (RRF only) vs +SiliconFlow rerank.

对每条 eval case, 用 resume_text 构造 query, ground-truth = 该 case 对应的 eval JD.
指标: Recall@3, Recall@5, MRR.

注意: baseline 使用当前配置的 embedding backend/model.
reranker 只能和同一 collection、同一 query mode 下的 baseline 比较.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_EVAL_PATH = Path("data/eval/real_jd_cases.jsonl")
DEFAULT_OUTPUT_DIR = Path("data/eval/reports/retrieval")


def build_query(case: dict, mode: str = "resume_brief") -> str:
    if mode == "title":
        title = case.get("title") or ""
        return f"找相关岗位 JD: {title}"
    if mode == "keywords":
        return _extract_keywords(case.get("resume_text", ""))
    resume_brief = case.get("resume_text", "")[:500]
    return f"找匹配这份简历的目标岗位 JD:\n{resume_brief}"


_SKILL_KEYWORDS = [
    "Python", "FastAPI", "LangGraph", "LangChain", "RAG", "Qdrant", "BM25",
    "RRF", "Agent", "SQLAlchemy", "PostgreSQL", "Docker", "pytest", "SSE",
    "DeepSeek", "bge-m3", "bge-reranker", "MCP", "Next.js",
]


def _extract_keywords(resume_text: str) -> str:
    hits = [kw for kw in _SKILL_KEYWORDS if kw.lower() in resume_text.lower()]
    return "找相关岗位 JD, 关键技能: " + " ".join(hits) if hits else "找软件工程师岗位"


def compute_metrics(ranked_jd_ids: list[str], gt_jd_id: str, ks: tuple[int, ...] = (3, 5)) -> dict:
    hits = {k: 0 for k in ks}
    mrr = 0.0
    for rank, jd_id in enumerate(ranked_jd_ids, start=1):
        if jd_id == gt_jd_id:
            mrr = 1.0 / rank
            for k in ks:
                if rank <= k:
                    hits[k] = 1
            break
    return {"mrr": mrr, **{f"recall_at_{k}": hits[k] for k in ks}}


async def run_ab(eval_path: Path, top_k_pool: int = 20, query_mode: str = "resume_brief") -> dict:
    from app.rag.retriever import hybrid_search
    from app.rag.reranker_api import rerank

    cases = [
        json.loads(line) for line in eval_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]

    baseline_per_case = []
    reranked_per_case = []
    for case in cases:
        case_id = case.get("id") or case.get("case_id")
        gt_jd_id = f"eval_{case_id}"
        query = build_query(case, mode=query_mode)
        logger.info("Case %s [%s]: gt=%s query=%r", case_id, query_mode, gt_jd_id, query[:80])

        baseline = await hybrid_search(query, top_k=top_k_pool, use_rerank=False)
        baseline_ids = [hit.id for hit in baseline]
        baseline_metrics = compute_metrics(baseline_ids, gt_jd_id)
        baseline_per_case.append({
            "case_id": case_id,
            "title": (case.get("title") or case["jd_text"][:60]),
            "gt_jd_id": gt_jd_id,
            "ranked_jd_ids": baseline_ids,
            "metrics": baseline_metrics,
        })
        logger.info("  baseline: %s", baseline_metrics)

        if not baseline:
            reranked_per_case.append({
                "case_id": case_id,
                "gt_jd_id": gt_jd_id,
                "ranked_jd_ids": [],
                "metrics": {"mrr": 0.0, "recall_at_3": 0, "recall_at_5": 0},
                "rerank_error": "no baseline candidates",
            })
            continue

        try:
            ranked = await rerank(query, [hit.text for hit in baseline], top_k=top_k_pool)
            reranked_ids = [baseline[idx].id for idx, _ in ranked]
        except Exception:
            logger.exception("Rerank failed for case %s", case_id)
            reranked_ids = baseline_ids

        reranked_metrics = compute_metrics(reranked_ids, gt_jd_id)
        reranked_per_case.append({
            "case_id": case_id,
            "gt_jd_id": gt_jd_id,
            "ranked_jd_ids": reranked_ids,
            "metrics": reranked_metrics,
        })
        logger.info("  reranked: %s", reranked_metrics)

    def avg(rows, key):
        vals = [r["metrics"][key] for r in rows]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    metric_keys = ["mrr", "recall_at_3", "recall_at_5"]
    baseline_avg = {k: avg(baseline_per_case, k) for k in metric_keys}
    reranked_avg = {k: avg(reranked_per_case, k) for k in metric_keys}
    delta = {k: round(reranked_avg[k] - baseline_avg[k], 4) for k in metric_keys}

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "embedding_backend": _setting("EMBEDDING_BACKEND"),
            "embedding_model": _setting("EMBEDDING_MODEL"),
            "reranker_model": _setting("RERANKER_MODEL"),
            "reranker_provider": "siliconflow",
            "top_k_pool": top_k_pool,
            "query_mode": query_mode,
        },
        "total": len(cases),
        "baseline": baseline_avg,
        "reranked": reranked_avg,
        "delta": delta,
        "caveat": "baseline uses the configured embedding backend/model shown above. "
                  "Only compare reranker against the same collection and query mode.",
        "baseline_cases": baseline_per_case,
        "reranked_cases": reranked_per_case,
    }


def _setting(key: str) -> str:
    from app.core.config import settings
    return getattr(settings, key, "")


def write_report(report: dict, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"retrieval_ab_{ts}.json"
    md_path = output_dir / f"retrieval_ab_{ts}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_format_md(report), encoding="utf-8")
    return json_path, md_path


def _format_md(report: dict) -> str:
    lines = [
        "# Retrieval A/B: Baseline (RRF) vs +SiliconFlow Rerank",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Total cases: `{report['total']}`",
        f"- Embedding: `{report['config']['embedding_backend']}` ({report['config']['embedding_model']})",
        f"- Reranker: `{report['config']['reranker_model']}` via {report['config']['reranker_provider']}",
        f"- Top-K pool: `{report['config']['top_k_pool']}`",
        "",
        "> " + report["caveat"],
        "",
        "## Summary",
        "",
        "| metric | baseline (RRF) | + rerank | delta |",
        "|---|---:|---:|---:|",
    ]
    for k in ["recall_at_3", "recall_at_5", "mrr"]:
        b = report["baseline"][k]
        r = report["reranked"][k]
        d = report["delta"][k]
        sign = "+" if d >= 0 else ""
        lines.append(f"| {k} | {b:.4f} | {r:.4f} | {sign}{d:.4f} |")
    lines += ["", "## Per-case", "",
              "| case_id | baseline R@3 | rerank R@3 | baseline R@5 | rerank R@5 | baseline MRR | rerank MRR |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for b, r in zip(report["baseline_cases"], report["reranked_cases"]):
        lines.append(
            f"| {b['case_id']} | {b['metrics']['recall_at_3']} | {r['metrics']['recall_at_3']} | "
            f"{b['metrics']['recall_at_5']} | {r['metrics']['recall_at_5']} | "
            f"{b['metrics']['mrr']:.4f} | {r['metrics']['mrr']:.4f} |"
        )
    return "\n".join(lines) + "\n"


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, default=DEFAULT_EVAL_PATH)
    parser.add_argument("--top-k-pool", type=int, default=20, help="candidates fed into rerank")
    parser.add_argument(
        "--query-mode",
        choices=["resume_brief", "title", "keywords"],
        default="resume_brief",
        help="resume_brief (long resume, default) | title (short JD-title query) | keywords (skill keywords)",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    report = await run_ab(args.file, top_k_pool=args.top_k_pool, query_mode=args.query_mode)
    json_path, md_path = write_report(report, args.output_dir)
    logger.info("Wrote retrieval A/B JSON: %s", json_path)
    logger.info("Wrote retrieval A/B Markdown: %s", md_path)
    logger.info("Summary: baseline=%s reranked=%s delta=%s", report["baseline"], report["reranked"], report["delta"])


if __name__ == "__main__":
    asyncio.run(main())
