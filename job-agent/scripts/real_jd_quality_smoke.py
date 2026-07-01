"""Fetch a few real job posts and run LLM quality smoke checks."""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import re
import sys
import textwrap
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent.prompts import load_prompt
from app.core.config import settings
from app.services.llm import llm_complete, parse_llm_json_object


USER_AGENT = "job-agent-quality-smoke/0.1"
SOURCES = {
    "arbeitnow": "https://www.arbeitnow.com/api/job-board-api",
    "remoteok": "https://remoteok.com/api",
}
KEYWORDS = [
    "ai",
    "artificial intelligence",
    "machine learning",
    "ml",
    "llm",
    "rag",
    "agent",
    "python",
    "backend",
    "data scientist",
    "data engineer",
    "nlp",
    "fastapi",
]
PHRASE_KEYWORDS = [
    keyword
    for keyword in KEYWORDS
    if keyword not in {"ai", "ml"}
]
SHORT_KEYWORDS = {"ai", "ml"}

RESUME_TEXT = """候选人简历摘要：
- 2 年 Python 后端与 AI Agent 项目经验，熟悉 FastAPI、SQLAlchemy、PostgreSQL。
- 构建过基于 LangGraph 的求职助手 Agent，包含 planner、retriever、analyzer、rewriter 节点。
- 熟悉 RAG 检索链路，使用 Qdrant、BM25、RRF、hash/local embedding 做 JD 检索验证。
- 写过 pytest 集成测试、SSE 接口测试、Docker Compose 隔离环境。
- 了解 LLM prompt 版本管理、JSON 输出解析、LLM-as-Judge 评测思路。
"""


@dataclass(frozen=True)
class JobPost:
    source: str
    title: str
    company: str
    url: str
    description: str
    score: int


def _fetch_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def _clean_html(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(p|li|h[1-6]|ul|ol|div)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _keyword_score(text: str) -> int:
    lowered = text.lower()
    score = sum(1 for keyword in PHRASE_KEYWORDS if keyword in lowered)
    score += sum(
        1
        for keyword in SHORT_KEYWORDS
        if re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", lowered)
    )
    return score


def _normalize_jobs(raw: Any, source: str) -> list[JobPost]:
    if source == "arbeitnow":
        items = raw.get("data", []) if isinstance(raw, dict) else []
        return [
            _job(
                source=source,
                title=item.get("title") or "",
                company=item.get("company_name") or "",
                url=item.get("url") or "",
                description=item.get("description") or "",
            )
            for item in items
        ]

    if source == "remoteok":
        items = raw[1:] if isinstance(raw, list) else []
        return [
            _job(
                source=source,
                title=item.get("position") or "",
                company=item.get("company") or "",
                url=item.get("url") or item.get("apply_url") or "",
                description=item.get("description") or "",
            )
            for item in items
        ]

    return []


def _job(source: str, title: str, company: str, url: str, description: str) -> JobPost:
    cleaned = _clean_html(description)
    score = _keyword_score(" ".join([title, cleaned]))
    return JobPost(
        source=source,
        title=title.strip() or "Untitled",
        company=company.strip() or "Unknown",
        url=url.strip(),
        description=cleaned,
        score=score,
    )


def fetch_real_jobs(limit: int) -> list[JobPost]:
    jobs: list[JobPost] = []
    for source, url in SOURCES.items():
        try:
            raw = _fetch_json(url)
        except Exception as exc:
            print(f"source_skip: {source} ({type(exc).__name__}: {exc})")
            continue
        jobs.extend(_normalize_jobs(raw, source))

    seen: set[str] = set()
    filtered: list[JobPost] = []
    for job in sorted(jobs, key=lambda item: (item.score, len(item.description)), reverse=True):
        key = f"{job.source}:{job.url or job.title}:{job.company}"
        if key in seen or job.score <= 0 or len(job.description) < 300:
            continue
        seen.add(key)
        filtered.append(job)
        if len(filtered) >= limit:
            break

    if len(filtered) < limit:
        raise RuntimeError(f"only found {len(filtered)} matching real job posts")
    return filtered


async def analyze_job(job: JobPost) -> dict[str, Any]:
    prompt = load_prompt("analyze").format(
        jd_context=job.description[:3500],
        resume_text=RESUME_TEXT,
        user_message=f"请分析这份简历与真实岗位 {job.title} 的匹配度。",
    )
    raw = await llm_complete(prompt=prompt, max_tokens=2400, temperature=0.1)
    return parse_llm_json_object(raw)


async def rewrite_for_job(job: JobPost, analysis: dict[str, Any]) -> dict[str, Any]:
    prompt = load_prompt("rewrite").format(
        gap_analysis=json.dumps(analysis, ensure_ascii=False),
        user_message=f"请针对真实岗位 {job.title} 改写项目经历，突出最相关的能力。",
    )
    raw = await llm_complete(prompt=prompt, max_tokens=1800, temperature=0.1)
    return parse_llm_json_object(raw)


def quality_flags(analysis: dict[str, Any], rewrite: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    score = analysis.get("match_score")
    if not isinstance(score, int | float) or not 0 <= float(score) <= 100:
        flags.append("bad_match_score")
    if not isinstance(analysis.get("gaps"), list):
        flags.append("bad_gaps")
    if not analysis.get("summary"):
        flags.append("missing_summary")
    sections = rewrite.get("sections")
    if not isinstance(sections, list) or not sections:
        flags.append("empty_rewrite_sections")
    elif not sections[0].get("rewritten"):
        flags.append("empty_rewritten_text")
    return flags


async def run(limit: int) -> None:
    jobs = fetch_real_jobs(limit)
    print(f"backend: {settings.LLM_BACKEND}")
    print(f"model: {settings.LLM_MODEL}")
    print(f"jobs: {len(jobs)}")

    for index, job in enumerate(jobs, start=1):
        analysis = await analyze_job(job)
        rewrite = await rewrite_for_job(job, analysis)
        flags = quality_flags(analysis, rewrite)
        gaps = analysis.get("gaps") or []
        first_gap = gaps[0].get("requirement") if gaps and isinstance(gaps[0], dict) else ""
        sections = rewrite.get("sections") or []
        rewritten = sections[0].get("rewritten") if sections and isinstance(sections[0], dict) else ""

        print()
        print(f"[{index}] {job.title} | {job.company} | {job.source}")
        print(f"url: {job.url}")
        print(f"keyword_score: {job.score}")
        print(f"match_score: {analysis.get('match_score')}")
        print(f"flags: {','.join(flags) if flags else 'OK'}")
        print(f"summary: {analysis.get('summary', '')[:240]}")
        print(f"first_gap: {str(first_gap)[:240]}")
        print("rewrite_preview:")
        print(textwrap.shorten(str(rewritten), width=320, placeholder="..."))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default=None, help="override LLM_BACKEND, e.g. openai")
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()

    if args.backend:
        settings.LLM_BACKEND = args.backend

    asyncio.run(run(args.limit))


if __name__ == "__main__":
    main()
