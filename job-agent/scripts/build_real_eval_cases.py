"""Build a small, reproducible JSONL eval set from public job-board APIs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.real_jd_quality_smoke import RESUME_TEXT, JobPost, fetch_real_jobs


DEFAULT_OUTPUT = Path("data/eval/real_jd_cases.jsonl")


def _expected_gaps(job: JobPost) -> list[str]:
    text = f"{job.title}\n{job.description}".lower()
    gaps: list[str] = []

    if any(token in text for token in ("senior", "lead", "5 years", "5+ years", "mehrjährige")):
        gaps.append("候选人经验年限可能不足以覆盖 senior/lead 或多年生产经验要求")
    if any(token in text for token in ("aws", "azure", "gcp", "cloud")):
        gaps.append("简历中缺少明确云平台部署与运维经验")
    if any(token in text for token in ("kubernetes", "terraform", "ansible", "openstack")):
        gaps.append("简历中缺少基础设施、Kubernetes 或 IaC 相关项目经验")
    if any(token in text for token in ("llm", "genai", "generative ai", "rag", "agent")):
        gaps.append("需要补充生产级 GenAI/LLM 项目的规模、可靠性和业务指标")
    if any(token in text for token in ("data", "analytics", "etl", "pipeline")):
        gaps.append("简历中缺少数据管道、分析或 ETL 项目的明确证据")

    if not gaps:
        gaps.append("需要更明确地对齐 JD 中的核心技术栈和业务场景")
    return gaps[:4]


def _expected_rewrite_points(job: JobPost) -> list[str]:
    text = f"{job.title}\n{job.description}".lower()
    points = [
        "突出 Python、FastAPI、LangGraph、RAG 与可测试工程闭环",
        "补充量化指标、部署环境、系统可靠性和业务结果",
    ]
    if any(token in text for token in ("llm", "genai", "generative ai", "rag", "agent")):
        points.append("强化 Agent 编排、检索增强生成和 LLM 输出稳定性经验")
    if any(token in text for token in ("cloud", "aws", "azure", "gcp", "kubernetes")):
        points.append("如属实，补充云平台、容器化部署和生产运维经验")
    return points[:4]


def _case_from_job(job: JobPost, index: int) -> dict:
    case_type = "high_relevance" if job.score >= 5 else "medium_relevance" if job.score >= 2 else "low_relevance"
    return {
        "id": f"real_jd_{index:03d}",
        "case_type": case_type,
        "keyword_score": job.score,
        "source": job.source,
        "source_url": job.url,
        "title": job.title,
        "company": job.company,
        "resume_text": RESUME_TEXT,
        "jd_text": "\n".join(
            [
                f"岗位：{job.title}",
                f"公司：{job.company}",
                f"来源：{job.source}",
                "",
                job.description,
            ]
        ),
        "expected_gaps": _expected_gaps(job),
        "expected_rewrite_points": _expected_rewrite_points(job),
    }


def build_cases(limit: int) -> list[dict]:
    jobs = fetch_real_jobs(limit)
    return [_case_from_job(job, index) for index, job in enumerate(jobs, start=1)]


def write_jsonl(cases: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "\n".join(json.dumps(case, ensure_ascii=False) for case in cases) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    cases = build_cases(args.limit)
    write_jsonl(cases, args.output)

    print(f"wrote: {args.output}")
    print(f"cases: {len(cases)}")
    for case in cases:
        print(
            f"- {case['id']} | {case['case_type']} | score={case['keyword_score']} | "
            f"{case['title']} | {case['company']} | {case['source']}"
        )


if __name__ == "__main__":
    main()
