"""Smoke test the chat SSE endpoint with the configured backend."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from collections.abc import Iterable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings


def _parse_sse(lines: Iterable[str]) -> list[dict]:
    events: list[dict] = []
    current: dict[str, list[str] | str] = {"event": "message", "data": []}

    def flush() -> None:
        data_lines = current.get("data", [])
        if not data_lines:
            return
        event = str(current.get("event") or "message")
        data = "\n".join(data_lines if isinstance(data_lines, list) else [str(data_lines)])
        events.append({"event": event, "data": json.loads(data)})

    for raw_line in lines:
        line = raw_line.rstrip("\r")
        if not line:
            flush()
            current = {"event": "message", "data": []}
            continue
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        value = value[1:] if value.startswith(" ") else value
        if field == "event":
            current["event"] = value
        elif field == "data":
            data = current.setdefault("data", [])
            assert isinstance(data, list)
            data.append(value)

    flush()
    return events


async def _seed_jds() -> None:
    from app.models.db import async_engine
    from scripts.ingest import ingest_jds

    await ingest_jds(write_vectors=True)
    await async_engine.dispose()


def _assert_events(events: list[dict]) -> None:
    event_types = [event["event"] for event in events]
    required = ["conversation", "node:planner", "node:retriever", "node:analyzer", "complete", "done"]
    missing = [event for event in required if event not in event_types]
    if missing:
        raise AssertionError(f"missing SSE events: {missing}; got {event_types}")
    if "error" in event_types:
        error_event = next(event for event in events if event["event"] == "error")
        raise AssertionError(f"SSE error event: {error_event['data']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default=None, help="override LLM_BACKEND, e.g. openai")
    parser.add_argument(
        "--message",
        default="我的简历包含 Python 和 FastAPI 项目，请分析 AI Agent 实习 JD 的匹配度",
    )
    args = parser.parse_args()

    if args.backend:
        settings.LLM_BACKEND = args.backend

    asyncio.run(_seed_jds())

    from fastapi.testclient import TestClient

    from app.main import app

    conversation_id = f"chat-smoke-{uuid.uuid4().hex}"
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/chat/stream",
            json={"conversation_id": conversation_id, "message": args.message},
        ) as response:
            response.raise_for_status()
            events = _parse_sse(response.iter_lines())

    _assert_events(events)
    event_types = [event["event"] for event in events]
    analyzer_event = next(event for event in events if event["event"] == "node:analyzer")
    analysis = analyzer_event["data"].get("gap_analysis", {})
    print(f"backend: {settings.LLM_BACKEND}")
    print(f"conversation_id: {conversation_id}")
    print(f"events: {','.join(event_types)}")
    print(f"match_score: {analysis.get('match_score')}")


if __name__ == "__main__":
    main()
